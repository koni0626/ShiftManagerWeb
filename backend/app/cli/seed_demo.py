"""Explicit local demo command; never runs automatically in the API."""

import json
import secrets
from datetime import timedelta, time
from pathlib import Path
from sqlalchemy import select
from app import models as m
from app.db import SessionLocal
from app.policies import Actor
from app.repositories import ScopedRepository
from app.services.auth_service import hasher
from app.services.common import today
from app.services.visit_service import VisitService


def main():
    with SessionLocal() as db:
        if db.scalar(select(m.User.id).limit(1)):
            print("Existing data found; demo creation skipped.")
            return
        credentials = {}
        for login, name, role in (
            ("admin", "システム管理者", "system_admin"),
            ("owner", "高橋 由紀", "owner"),
            ("member", "佐藤 陽子", "member"),
        ):
            password = secrets.token_urlsafe(15)
            user = m.User(
                login_id=login,
                name=name,
                role=role,
                password_hash=hasher.hash(password),
            )
            db.add(user)
            db.flush()
            credentials[login] = {"password": password, "id": user.id}
        company = m.Company(name="こもれびケアサービス（サンプル）")
        db.add(company)
        db.flush()
        scope = m.OwnerScope(
            company_id=company.id,
            owner_user_id=credentials["owner"]["id"],
            name="こもれびケア",
        )
        db.add(scope)
        db.flush()
        actor = Actor(credentials["owner"]["id"], "高橋 由紀", "owner", scope.id)
        r = ScopedRepository(db, actor, scope.id)
        branches = [
            r.add(m.Branch, name=name, address=address)
            for name, address in (
                ("中央営業所", "東京都千代田区"),
                ("東営業所", "東京都台東区"),
            )
        ]
        services = [
            r.add(m.Service, name=name, duration=duration, jobs=[job])
            for name, duration, job in (
                ("面談・モニタリング", 30, "ケアマネジャー"),
                ("身体介護", 60, "ヘルパー"),
                ("生活援助", 60, "ヘルパー"),
            )
        ]
        people = []
        for i, (name, job) in enumerate(
            (
                ("田中 美咲", "ケアマネジャー"),
                ("佐藤 陽子", "ヘルパー"),
                ("鈴木 翔太", "ヘルパー"),
                ("高橋 由紀", "兼務"),
            )
        ):
            p = r.add(
                m.Staff,
                name=name,
                job=job,
                user_id=credentials["member"]["id"] if i == 1 else None,
                service_ids=[x.id for x in services if job in x.jobs or job == "兼務"],
                weekdays=list(range(7)),
                start=time(9),
                end=time(18),
                break_start=time(12),
                break_end=time(13),
            )
            people.append(p)
            for b in branches if i in (1, 3) else branches[:1]:
                r.add(
                    m.Membership,
                    staff_id=p.id,
                    branch_id=b.id,
                    valid_from=today() - timedelta(days=90),
                )
        clients = []
        for i, name in enumerate(("山田", "伊藤", "中村", "渡辺", "小林", "加藤")):
            c = r.add(
                m.Client,
                name=f"{name}（架空）",
                label=f"{name}様",
                address="",
                guide="架空のサンプルです。実際の訪問先ではありません。",
                latitude=35.68 + i * 0.004,
                longitude=139.75 + i * 0.006,
                geocode_status="resolved",
                coordinate_source="manual",
                weekdays=list(range(7)),
            )
            clients.append(c)
            for b in branches:
                r.add(m.ClientBranch, client_id=c.id, branch_id=b.id)
        monday = today() - timedelta(days=today().weekday())
        for offset in range(14):
            for i, p in enumerate(people[:3]):
                service = services[0 if i == 0 else 1 + (offset % 2)]
                v = r.add(
                    m.Visit,
                    branch_id=branches[1 if i == 1 and offset % 2 else 0].id,
                    client_id=clients[(offset + i) % len(clients)].id,
                    service_id=service.id,
                    date=monday + timedelta(days=offset),
                    start=time((9, 10, 14)[i], 30),
                    duration=service.duration,
                    people=1,
                )
                r.add(m.Assignment, visit_id=v.id, staff_id=p.id)
        r.add(
            m.RequestWindow,
            month=today().strftime("%Y-%m"),
            deadline=today() + timedelta(days=20),
        )
        (
            Path(__file__).resolve().parents[3] / ".local" / "demo-accounts.json"
        ).write_text(
            json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        db.commit()
        # Publish several sample visits through the same validation as the API.
        svc = VisitService(db, actor, scope.id)
        ids = [(v.id, v.version) for v in svc.repo.all(m.Visit) if v.date >= today()][
            :9
        ]
        for id, version in ids:
            svc.transition(id, "confirm", version)
        (
            Path(__file__).resolve().parents[3] / ".local" / "demo-accounts.json"
        ).write_text(
            json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("Demo created. Login credentials: .local/demo-accounts.json")


if __name__ == "__main__":
    main()
