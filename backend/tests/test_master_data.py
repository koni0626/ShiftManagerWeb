from conftest import login


def test_master_registration_membership_and_pay_history(client, fixture):
    login(client, "owner-a")
    root = f"/api/v1/scopes/{fixture['a']['scope'].id}"
    service = client.post(
        root + "/services",
        json={"name": "買い物同行", "duration": 45, "people": 1, "jobs": ["ヘルパー"]},
    )
    assert service.status_code == 200, service.text
    branches = [fixture["a"]["branch"].id, fixture["a"]["second"].id]
    response = client.post(
        root + "/staff",
        json={
            "name": "新しいスタッフ",
            "branch_ids": branches,
            "service_ids": [service.json()["id"]],
        },
    )
    assert response.status_code == 200, response.text
    sid = response.json()["id"]
    member = client.post(
        root + "/members", json={"staff_id": sid, "login_id": "new-member"}
    )
    assert member.status_code == 200, member.text
    assert "setup_token" in member.json()
    for date, amount in [("2026-01-01", 1200), ("2026-04-01", 1300)]:
        assert (
            client.post(
                root + f"/staff/{sid}/pay-terms",
                json={
                    "effective_from": date,
                    "employment": "パート",
                    "basis": "hourly",
                    "amount": amount,
                },
            ).status_code
            == 200
        )
    data = client.get(root + "/workspace").json()
    staff = next(p for p in data["staff"] if p["id"] == sid)
    assert set(staff["branch_ids"]) == set(branches)
    assert staff["login_id"] == "new-member"
    assert [t["amount"] for t in data["pay_terms"] if t["staff_id"] == sid] == [
        1200,
        1300,
    ]


def test_cannot_deactivate_staff_with_future_draft(client, fixture):
    login(client, "owner-a")
    a = fixture["a"]
    root = f"/api/v1/scopes/{a['scope'].id}"
    response = client.patch(
        root + f"/staff/{a['staff'].id}",
        json={
            "expected_version": 1,
            "name": "Staff a",
            "active": False,
            "branch_ids": [a["branch"].id, a["second"].id],
            "service_ids": [a["service"].id],
        },
    )
    assert response.status_code == 409, response.text
