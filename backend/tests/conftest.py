import json
import os
from datetime import timedelta, time
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

credentials = json.loads(
    (Path(__file__).resolve().parents[2] / ".local/database.json").read_text()
)
os.environ["DATABASE_URL"] = (
    f"postgresql+psycopg://atelier_app:{credentials['app']}@127.0.0.1:55434/atelier_test"
)
os.environ["MIGRATION_DATABASE_URL"] = (
    f"postgresql+psycopg://atelier_admin:{credentials['admin']}@127.0.0.1:55434/atelier_test"
)
from app import models as m
from app.main import app
from app.services.auth_service import hasher
from app.services.common import today
from fastapi.testclient import TestClient

PASSWORD = "Atelier-test-password-123"


@pytest.fixture(scope="session", autouse=True)
def migrate():
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture()
def fixture():
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    assert engine.url.database == "atelier_test" and engine.url.port == 55434
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE " + ",".join(m.Base.metadata.tables.keys()) + " CASCADE")
        )
    data = {}
    from sqlalchemy.orm import Session

    with Session(engine, expire_on_commit=False) as db:
        company = m.Company(name="テスト会社")
        db.add(company)
        db.flush()
        password_hash = hasher.hash(PASSWORD)
        admin = m.User(
            name="管理者",
            login_id="admin",
            role="system_admin",
            password_hash=password_hash,
        )
        db.add(admin)
        db.flush()
        data["admin"] = admin
        for key in ("a", "b"):
            owner = m.User(
                name=f"Owner {key}",
                login_id=f"owner-{key}",
                role="owner",
                password_hash=password_hash,
            )
            member = m.User(
                name=f"Member {key}",
                login_id=f"member-{key}",
                role="member",
                password_hash=password_hash,
            )
            db.add_all([owner, member])
            db.flush()
            scope = m.OwnerScope(
                company_id=company.id, owner_user_id=owner.id, name=key
            )
            db.add(scope)
            db.flush()
            keys = {"company_id": company.id, "scope_id": scope.id}
            branch = m.Branch(**keys, name=f"Branch {key}")
            second = m.Branch(**keys, name=f"Second {key}")
            service = m.Service(**keys, name="生活援助", jobs=["ヘルパー"])
            db.add_all([branch, second, service])
            db.flush()
            staff = m.Staff(
                **keys,
                user_id=member.id,
                name=f"Staff {key}",
                weekdays=list(range(7)),
                service_ids=[service.id],
                start=time(8),
                end=time(20),
            )
            client = m.Client(
                **keys,
                name=f"Client {key}",
                label=f"{key}様",
                address="サンプル住所",
                private_note="SECRET_PRIVATE_NOTE",
                latitude=35.0,
                longitude=139.0,
                geocode_status="resolved",
            )
            db.add_all([staff, client])
            db.flush()
            for b in (branch, second):
                db.add(
                    m.Membership(
                        **keys,
                        staff_id=staff.id,
                        branch_id=b.id,
                        valid_from=today() - timedelta(days=100),
                    )
                )
                db.add(m.ClientBranch(**keys, client_id=client.id, branch_id=b.id))
            db.add(
                m.RequestWindow(
                    **keys,
                    month=today().strftime("%Y-%m"),
                    deadline=today() + timedelta(days=20),
                )
            )
            visit = m.Visit(
                **keys,
                branch_id=branch.id,
                client_id=client.id,
                service_id=service.id,
                date=today(),
                start=time(9),
                duration=60,
                people=1,
            )
            db.add(visit)
            db.flush()
            db.add(m.Assignment(**keys, visit_id=visit.id, staff_id=staff.id))
            data[key] = {
                "owner": owner,
                "member": member,
                "scope": scope,
                "branch": branch,
                "second": second,
                "staff": staff,
                "client": client,
                "service": service,
                "visit": visit,
                "keys": keys,
            }
        db.commit()
    engine.dispose()
    return data


@pytest.fixture()
def client(fixture):
    with TestClient(app, headers={"origin": "http://127.0.0.1:5194"}) as client:
        yield client


def login(client, login_id):
    response = client.post(
        "/api/v1/auth/login", json={"login_id": login_id, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["x-csrf-token"] = client.cookies["atelier_csrf"]
    return response.json()
