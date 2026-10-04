"""Bounded, leased worker. External calls are disabled until permanent use is configured."""

import argparse
import time
from datetime import timedelta
import httpx
from sqlalchemy import select, or_, and_
from app import models as m
from app.core.config import settings
from app.db import SessionLocal, context


def run_one():
    if not settings.mapbox_token or not settings.geocoding_permanent_enabled:
        return False
    with SessionLocal() as db:
        context(db, role="system_admin")
        abandoned = db.scalar(
            select(m.GeocodeJob)
            .where(
                m.GeocodeJob.status == "running",
                m.GeocodeJob.attempts >= 3,
                m.GeocodeJob.lease_until < m.utcnow(),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if abandoned:
            abandoned.status = "failed"
            client = db.scalar(
                select(m.Client)
                .where(m.Client.id == abandoned.client_id)
                .with_for_update()
            )
            if (
                client.address_revision == abandoned.address_revision
                and client.geometry_version == abandoned.geometry_version
            ):
                client.geocode_status = "failed"
                client.version += 1
            db.commit()
            return True
        job = db.scalar(
            select(m.GeocodeJob)
            .where(
                m.GeocodeJob.attempts < 3,
                m.GeocodeJob.next_run <= m.utcnow(),
                or_(
                    m.GeocodeJob.status == "queued",
                    and_(
                        m.GeocodeJob.status == "running",
                        m.GeocodeJob.lease_until < m.utcnow(),
                    ),
                ),
            )
            .order_by(m.GeocodeJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        client = db.get(m.Client, job.client_id)
        scope = db.get(m.OwnerScope, client.scope_id)
        owner, company = (
            db.get(m.User, scope.owner_user_id),
            db.get(m.Company, scope.company_id),
        )
        if (
            not client.active
            or not owner.active
            or not company.active
            or client.address_revision != job.address_revision
            or client.geometry_version != job.geometry_version
        ):
            job.status = "stale"
            db.commit()
            return True
        job.status, job.lease_token, job.lease_until = (
            "running",
            m.uid(),
            m.utcnow() + timedelta(minutes=2),
        )
        job.attempts += 1
        client.geocode_status = "running"
        id, lease, address = job.id, job.lease_token, client.address
        db.commit()
    try:
        response = httpx.get(
            "https://api.mapbox.com/search/geocode/v6/forward",
            params={
                "q": address,
                "country": "jp",
                "language": "ja",
                "limit": 5,
                "permanent": "true",
                "access_token": settings.mapbox_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        candidates = []
        for feature in features:
            props = feature.get("properties", {})
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if len(coordinates) < 2:
                continue
            candidates.append(
                {
                    "latitude": coordinates[1],
                    "longitude": coordinates[0],
                    "label": props.get("full_address", props.get("name", "")),
                    "accuracy": props.get("coordinates", {}).get("accuracy", ""),
                    "confidence": props.get("match_code", {}).get("confidence", ""),
                    "feature_type": props.get("feature_type", ""),
                }
            )
        failure = None
    except (httpx.HTTPError, ValueError, TypeError):
        candidates, failure = [], "provider_error"
    with SessionLocal() as db:
        context(db, role="system_admin")
        job = db.scalar(
            select(m.GeocodeJob).where(m.GeocodeJob.id == id).with_for_update()
        )
        if job.lease_token != lease:
            return True
        client = db.scalar(
            select(m.Client).where(m.Client.id == job.client_id).with_for_update()
        )
        if (
            client.address_revision != job.address_revision
            or client.geometry_version != job.geometry_version
            or not client.active
        ):
            job.status = "stale"
            db.commit()
            return True
        if failure:
            job.status = "queued" if job.attempts < 3 else "failed"
            job.next_run = m.utcnow() + timedelta(seconds=60 * job.attempts)
            client.geocode_status = "queued" if job.status == "queued" else "failed"
        else:
            job.status = "done"
            client.candidates = candidates
            client.geocode_status = "needs_review" if candidates else "not_found"
            # Conservative acceptance: a single exact rooftop address match only.
            if (
                len(candidates) == 1
                and candidates[0]["feature_type"] == "address"
                and candidates[0]["confidence"] == "exact"
                and candidates[0]["accuracy"] == "rooftop"
            ):
                client.latitude, client.longitude = (
                    candidates[0]["latitude"],
                    candidates[0]["longitude"],
                )
                client.geocode_status, client.coordinate_source = (
                    "resolved",
                    "provider_auto",
                )
                client.geometry_version += 1
        client.version += 1
        db.commit()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        found = run_one()
        if args.once:
            break
        if not found:
            time.sleep(5)
