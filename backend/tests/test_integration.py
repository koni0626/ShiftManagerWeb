import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import models as m
from app.db import SessionLocal, context
from app.main import app
from app.services.common import today
from conftest import login


def root(f):
    return f"/api/v1/scopes/{f['a']['scope'].id}"


def visit_body(f, **changes):
    a = f["a"]
    return {
        "branch_id": a["branch"].id,
        "client_id": a["client"].id,
        "service_id": a["service"].id,
        "date": today().isoformat(),
        "start": "09:30",
        "duration": 60,
        "people": 1,
        "staff_ids": [a["staff"].id],
        **changes,
    }


def test_owner_isolation_and_admin(client, fixture):
    login(client, "owner-b")
    assert client.get(root(fixture) + "/workspace").status_code == 403
    login(client, "owner-a")
    data = client.get(root(fixture) + "/workspace").json()
    assert {x["id"] for x in data["staff"]} == {fixture["a"]["staff"].id}
    assert client.get("/api/v1/admin/overview").status_code == 403
    login(client, "admin")
    assert client.get(root(fixture) + "/workspace").status_code == 200
    assert len(client.get("/api/v1/admin/overview").json()["scopes"]) == 2


def test_postgres_rls_and_composite_foreign_key(fixture):
    with SessionLocal() as db:
        assert list(db.scalars(select(m.Client))) == []
        context(db, fixture["a"]["owner"].id, "owner", fixture["a"]["scope"].id)
        assert {c.id for c in db.scalars(select(m.Client))} == {
            fixture["a"]["client"].id
        }
        bad = m.ClientBranch(
            **fixture["a"]["keys"],
            client_id=fixture["a"]["client"].id,
            branch_id=fixture["b"]["branch"].id,
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert list(db.scalars(select(m.Client))) == []


def test_member_drafts_and_published_dto(client, fixture):
    login(client, "member-a")
    assert client.get(root(fixture) + "/workspace").status_code == 403
    assert client.get("/api/v1/me/schedule").json()["visits"] == []
    assert (
        client.post(root(fixture) + "/visits", json=visit_body(fixture)).status_code
        == 403
    )
    login(client, "owner-a")
    response = client.post(
        root(fixture) + f"/visits/{fixture['a']['visit'].id}/confirm",
        json={"expected_version": 1},
    )
    assert response.status_code == 200, response.text
    login(client, "member-a")
    response = client.get("/api/v1/me/schedule")
    assert len(response.json()["visits"]) == 1
    assert (
        "SECRET_PRIVATE_NOTE" not in response.text
        and "password_hash" not in response.text
        and "pay_terms" not in response.text
    )
    assert response.json()["visits"][0]["location"]["address"] == "サンプル住所"
    login(client, "member-b")
    assert client.get("/api/v1/me/schedule").json()["visits"] == []


def test_cross_branch_overlap_cannot_publish(client, fixture):
    login(client, "owner-a")
    response = client.post(
        root(fixture) + "/visits",
        json=visit_body(fixture, branch_id=fixture["a"]["second"].id),
    )
    assert response.status_code == 200, response.text
    result = client.post(
        root(fixture) + f"/visits/{response.json()['id']}/confirm",
        json={"expected_version": 1},
    )
    assert result.status_code == 422 and "重複" in result.text


def test_forged_reference_rejected(client, fixture):
    login(client, "owner-a")
    response = client.post(
        root(fixture) + "/visits",
        json=visit_body(fixture, branch_id=fixture["b"]["branch"].id),
    )
    assert response.status_code == 404


def test_drag_version_and_confirmed_lock(client, fixture):
    login(client, "owner-a")
    path = root(fixture) + f"/visits/{fixture['a']['visit'].id}"
    body = {
        "expected_version": 1,
        "target_date": today().isoformat(),
        "target_start": "10:00",
        "source_staff_id": fixture["a"]["staff"].id,
        "target_staff_id": fixture["a"]["staff"].id,
    }
    assert client.patch(path + "/position", json=body).status_code == 200
    assert client.patch(path + "/position", json=body).status_code == 409
    assert (
        client.post(path + "/confirm", json={"expected_version": 2}).status_code == 200
    )
    body["expected_version"] = 3
    assert client.patch(path + "/position", json=body).status_code == 409


def test_reopen_keeps_publication(client, fixture):
    login(client, "owner-a")
    path = root(fixture) + f"/visits/{fixture['a']['visit'].id}"
    assert (
        client.post(path + "/confirm", json={"expected_version": 1}).status_code == 200
    )
    assert (
        client.post(path + "/reopen", json={"expected_version": 2}).status_code == 200
    )
    assert (
        client.patch(
            path, json=visit_body(fixture, start="14:00", expected_version=3)
        ).status_code
        == 200
    )
    login(client, "member-a")
    v = client.get("/api/v1/me/schedule").json()["visits"][0]
    assert v["start"] == "09:00" and v["status"] == "readjusting"


def test_csrf_and_origin(client, fixture):
    login(client, "owner-a")
    client.headers.pop("x-csrf-token")
    assert (
        client.post(root(fixture) + "/branches", json={"name": "CSRF"}).status_code
        == 403
    )
    client.headers["x-csrf-token"] = client.cookies["atelier_csrf"]
    client.headers["origin"] = "https://evil.example"
    assert (
        client.post(root(fixture) + "/branches", json={"name": "CSRF"}).status_code
        == 403
    )


def test_requests_submit_withdraw_and_extra_fields(client, fixture):
    login(client, "member-a")
    path = "/api/v1/me/requests/" + today().strftime("%Y-%m")
    body = {"days": [{"date": today().isoformat(), "kind": "unavailable"}]}
    assert (
        client.put(
            path, json={**body, "staff_id": fixture["b"]["staff"].id}
        ).status_code
        == 422
    )
    assert client.put(path, json=body).status_code == 200
    assert (
        client.post(path + "/submit", json={"expected_version": 1}).status_code == 200
    )
    assert client.put(path, json={**body, "expected_version": 2}).status_code == 409
    login(client, "owner-a")
    result = client.post(
        root(fixture) + f"/visits/{fixture['a']['visit'].id}/confirm",
        json={"expected_version": 1},
    )
    assert result.status_code == 422 and "勤務不可" in result.text
    login(client, "member-a")
    assert (
        client.post(path + "/withdraw", json={"expected_version": 2}).status_code == 200
    )


def test_address_invalidates_location(client, fixture):
    login(client, "owner-a")
    a = fixture["a"]
    payload = {
        "name": "住所変更",
        "label": "A様",
        "branch_ids": [a["branch"].id],
        "address": "新しい住所",
        "expected_version": 1,
    }
    response = client.patch(root(fixture) + f"/clients/{a['client'].id}", json=payload)
    assert response.status_code == 200, response.text
    row = client.get(root(fixture) + "/workspace").json()["clients"][0]
    assert row["latitude"] is None and row["longitude"] is None
    assert row["address_revision"] == 2
    assert (
        client.patch(
            root(fixture) + f"/clients/{a['client'].id}/coordinates",
            json={"expected_version": 1, "latitude": 35, "longitude": 139},
        ).status_code
        == 409
    )


def test_account_disable_revokes_session(client, fixture):
    member = TestClient(app, headers={"origin": "http://127.0.0.1:5194"})
    login(member, "member-a")
    login(client, "owner-a")
    response = client.patch(
        root(fixture) + f"/staff/{fixture['a']['staff'].id}/account",
        json={"active": False},
    )
    assert response.status_code == 200, response.text
    assert member.get("/api/v1/me/schedule").status_code == 401
    member.close()


def test_setup_token_one_use_and_ownership(client, fixture):
    login(client, "owner-b")
    path = root(fixture) + f"/staff/{fixture['a']['staff'].id}/setup-token"
    assert client.post(path).status_code == 403
    login(client, "owner-a")
    token = client.post(path).json()["setup_token"]
    body = {"token": token, "password": "New-password-12345"}
    assert client.post("/api/v1/auth/setup", json=body).status_code == 200
    assert client.post("/api/v1/auth/setup", json=body).status_code == 422


def test_concurrent_conflicting_cards(client, fixture):
    from concurrent.futures import ThreadPoolExecutor

    login(client, "owner-a")

    def create(start):
        return client.post(
            root(fixture) + "/visits", json=visit_body(fixture, start=start)
        ).json()["id"]

    a, b = create("14:00"), create("16:00")
    headers = dict(client.headers)
    cookies = dict(client.cookies)

    def move(id):
        with TestClient(app, headers=headers, cookies=cookies) as c:
            return c.patch(
                root(fixture) + f"/visits/{id}",
                json=visit_body(fixture, start="14:30", expected_version=1),
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(move, [a, b])) == [200, 200]
    # Overlapping drafts are allowed, but neither may be published.
    for id in (a, b):
        assert (
            client.post(
                root(fixture) + f"/visits/{id}/confirm", json={"expected_version": 2}
            ).status_code
            == 422
        )
