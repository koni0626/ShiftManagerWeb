from sqlalchemy import select
from app import models as m
from app.db import SessionLocal, context
from app.core.config import settings
from app.workers.geocoding import run_one
from conftest import login


def queue(client, fixture, monkeypatch):
    monkeypatch.setattr(settings, "mapbox_token", "fake-test-token")
    monkeypatch.setattr(settings, "geocoding_permanent_enabled", True)
    login(client, "owner-a")
    path = (
        f"/api/v1/scopes/{fixture['a']['scope'].id}/clients/{fixture['a']['client'].id}"
    )
    assert (
        client.post(path + "/geocode", json={"expected_version": 1}).status_code == 200
    )
    return path


class Reply:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "features": [
                {
                    "geometry": {"coordinates": [140, 36]},
                    "properties": {
                        "feature_type": "address",
                        "full_address": "候補住所",
                        "coordinates": {"accuracy": "interpolated"},
                        "match_code": {"confidence": "medium"},
                    },
                }
            ]
        }


def test_ambiguous_result_is_not_published(client, fixture, monkeypatch):
    queue(client, fixture, monkeypatch)
    monkeypatch.setattr("app.workers.geocoding.httpx.get", lambda *a, **kw: Reply())
    assert run_one()
    with SessionLocal() as db:
        context(db, role="system_admin")
        row = db.get(m.Client, fixture["a"]["client"].id)
        assert row.geocode_status == "needs_review"
        assert row.candidates[0]["label"] == "候補住所"


def test_late_geocode_cannot_replace_manual_pin(client, fixture, monkeypatch):
    path = queue(client, fixture, monkeypatch)

    def lookup(*args, **kwargs):
        assert kwargs["params"]["permanent"] == "true"
        result = client.patch(
            path + "/coordinates",
            json={"expected_version": 2, "latitude": 33.3, "longitude": 133.3},
        )
        assert result.status_code == 200, result.text
        return Reply()

    monkeypatch.setattr("app.workers.geocoding.httpx.get", lookup)
    assert run_one()
    with SessionLocal() as db:
        context(db, role="system_admin")
        row = db.get(m.Client, fixture["a"]["client"].id)
        assert float(row.latitude) == 33.3 and row.coordinate_source == "manual"
        assert row.geocode_status == "resolved"
        assert db.scalar(select(m.GeocodeJob)).status == "stale"
