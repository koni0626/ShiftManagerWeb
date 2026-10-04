from datetime import timedelta
import pytest
from app.services.common import today
from conftest import login
from test_integration import root, visit_body


def staff_body(fixture, **changes):
    return {
        "name": "オーナー本人",
        "branch_ids": [fixture["a"]["branch"].id, fixture["a"]["second"].id],
        "service_ids": [fixture["a"]["service"].id],
        "weekdays": list(range(7)),
        **changes,
    }


def requests_body(**changes):
    return {"days": [{"date": today().isoformat(), "kind": "available"}], **changes}


def test_proxy_save_submit_and_member_sees_real_operator(client, fixture):
    owner = login(client, "owner-a")
    path = root(fixture) + f"/staff/{fixture['a']['staff'].id}/requests/{today():%Y-%m}"
    response = client.put(path, json=requests_body())
    assert response.status_code == 200, response.text
    response = client.post(path + "/submit", json={"expected_version": 1})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "submitted"
    data = client.get(root(fixture) + "/workspace").json()
    history = [h for h in data["history"] if h["action"] == "request_proxy"]
    assert len(history) == 2
    assert all(h["actor_id"] == owner["id"] for h in history)
    assert "Staff a" in history[0]["summary"] and "代理" in history[0]["summary"]
    login(client, "member-a")
    personal = client.get("/api/v1/me/schedule").json()
    assert personal["submissions"][0]["days"] == response.json()["days"]
    assert any("代理提出" in n["text"] for n in personal["notices"])


@pytest.mark.parametrize(
    "account,target_scope,target_staff,expected",
    [
        ("owner-b", "a", "a", 403),
        ("owner-a", "a", "b", 404),
        ("member-a", "a", "a", 403),
        ("member-b", "a", "a", 403),
        ("admin", "a", "a", 200),
    ],
)
def test_proxy_scope_and_role(
    client, fixture, account, target_scope, target_staff, expected
):
    login(client, account)
    path = f"/api/v1/scopes/{fixture[target_scope]['scope'].id}/staff/{fixture[target_staff]['staff'].id}/requests/{today():%Y-%m}"
    assert client.put(path, json=requests_body()).status_code == expected


def test_proxy_deadline_return_and_optimistic_lock(client, fixture):
    login(client, "owner-a")
    base = root(fixture)
    path = base + f"/staff/{fixture['a']['staff'].id}/requests/{today():%Y-%m}"
    assert (
        client.put(
            path, json=requests_body(staff_id=fixture["b"]["staff"].id)
        ).status_code
        == 422
    )
    row = client.put(path, json=requests_body()).json()
    assert client.put(path, json=requests_body(expected_version=999)).status_code == 409
    assert (
        client.post(path + "/submit", json={"expected_version": 1}).status_code == 200
    )
    assert client.put(path, json=requests_body(expected_version=2)).status_code == 409
    assert (
        client.post(
            base + "/request-windows",
            json={
                "month": f"{today():%Y-%m}",
                "deadline": (today() - timedelta(days=1)).isoformat(),
            },
        ).status_code
        == 200
    )
    assert (
        client.post(path + "/withdraw", json={"expected_version": 2}).status_code == 409
    )
    response = client.post(
        base + f"/request-submissions/{row['id']}/return",
        json={"expected_version": 2, "reason": "本人から時間変更の連絡"},
    )
    assert response.status_code == 200, response.text
    assert client.put(path, json=requests_body(expected_version=3)).status_code == 200
    assert (
        client.post(path + "/submit", json={"expected_version": 4}).status_code == 200
    )


def test_proxy_for_staff_without_login(client, fixture):
    login(client, "owner-a")
    base = root(fixture)
    staff = client.post(
        base + "/staff", json=staff_body(fixture, name="ログインを使わないスタッフ")
    ).json()
    path = base + f"/staff/{staff['id']}/requests/{today():%Y-%m}"
    assert client.put(path, json=requests_body()).status_code == 200
    assert (
        client.post(path + "/submit", json={"expected_version": 1}).status_code == 200
    )
    assert (
        client.patch(
            base + f"/staff/{staff['id']}",
            json=staff_body(fixture, expected_version=1, active=False),
        ).status_code
        == 200
    )
    assert client.put(path, json=requests_body(expected_version=2)).status_code == 409


def test_owner_create_profile_own_requests_and_visits(client, fixture):
    original = login(client, "owner-a")
    base = root(fixture)
    assert client.get("/api/v1/me/schedule").status_code == 403
    response = client.post(base + "/owner-profile", json=staff_body(fixture))
    assert response.status_code == 200, response.text
    staff_id = response.json()["id"]
    assert (
        client.post(base + "/owner-profile", json=staff_body(fixture)).status_code
        == 409
    )
    actor = client.get("/api/v1/auth/me").json()
    assert (
        actor["id"] == original["id"]
        and actor["role"] == "owner"
        and actor["staff_id"] == staff_id
    )
    data = client.get(base + "/workspace").json()
    staff = next(p for p in data["staff"] if p["id"] == staff_id)
    assert staff["account_role"] == "owner" and len(staff["branch_ids"]) == 2
    assert client.post(base + f"/staff/{staff_id}/setup-token").status_code == 403
    path = f"/api/v1/me/requests/{today():%Y-%m}"
    response = client.put(path, json=requests_body())
    assert response.status_code == 200, response.text
    assert (
        client.post(path + "/submit", json={"expected_version": 1}).status_code == 200
    )
    other = base + f"/staff/{fixture['a']['staff'].id}/requests/{today():%Y-%m}"
    assert client.put(other, json=requests_body()).status_code == 200
    visit = client.post(
        base + "/visits", json=visit_body(fixture, staff_ids=[staff_id], start="14:00")
    )
    assert visit.status_code == 200, visit.text
    assert (
        client.post(
            base + f"/visits/{visit.json()['id']}/confirm", json={"expected_version": 1}
        ).status_code
        == 200
    )
    personal = client.get("/api/v1/me/schedule").json()
    assert len(personal["submissions"]) == 1
    assert [v["id"] for v in personal["visits"]] == [visit.json()["id"]]
    login(client, "member-a")
    assert client.get("/api/v1/me/schedule").json()["visits"] == []


def test_owner_link_existing_preserves_schedule_and_prevents_takeover(client, fixture):
    login(client, "owner-a")
    base = root(fixture)
    assert (
        client.post(
            base + "/owner-profile/link",
            json={"staff_id": fixture["a"]["staff"].id, "expected_version": 1},
        ).status_code
        == 409
    )
    assert (
        client.post(
            base + "/owner-profile/link",
            json={"staff_id": fixture["b"]["staff"].id, "expected_version": 1},
        ).status_code
        == 404
    )
    staff = client.post(base + "/staff", json=staff_body(fixture)).json()
    visit = client.post(
        base + "/visits",
        json=visit_body(fixture, staff_ids=[staff["id"]], start="14:00"),
    ).json()
    path = base + f"/staff/{staff['id']}/requests/{today():%Y-%m}"
    assert client.put(path, json=requests_body()).status_code == 200
    assert (
        client.post(
            base + "/owner-profile/link",
            json={"staff_id": staff["id"], "expected_version": 999},
        ).status_code
        == 409
    )
    response = client.post(
        base + "/owner-profile/link",
        json={"staff_id": staff["id"], "expected_version": 1},
    )
    assert response.status_code == 200, response.text
    data = client.get(base + "/workspace").json()
    assert next(v for v in data["visits"] if v["id"] == visit["id"])["staff_ids"] == [
        staff["id"]
    ]
    assert len(client.get("/api/v1/me/schedule").json()["submissions"]) == 1
    assert (
        client.post(
            base + "/owner-profile/link",
            json={"staff_id": staff["id"], "expected_version": 2},
        ).status_code
        == 409
    )
    login(client, "admin")
    assert (
        client.post(base + "/owner-profile", json=staff_body(fixture)).status_code
        == 403
    )
    login(client, "member-a")
    assert (
        client.post(base + "/owner-profile", json=staff_body(fixture)).status_code
        == 403
    )


def test_inactive_owner_profile_preserves_management_access(client, fixture):
    login(client, "owner-a")
    base = root(fixture)
    staff = client.post(base + "/owner-profile", json=staff_body(fixture)).json()
    response = client.patch(
        base + f"/staff/{staff['id']}",
        json=staff_body(fixture, active=False, expected_version=1),
    )
    assert response.status_code == 200, response.text
    actor = login(client, "owner-a")
    assert actor["staff_id"] is None and actor["role"] == "owner"
    assert client.get(base + "/workspace").status_code == 200
    assert client.get("/api/v1/me/schedule").status_code == 403
    assert (
        client.post(base + "/owner-profile", json=staff_body(fixture)).status_code
        == 409
    )
