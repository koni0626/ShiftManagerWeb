from datetime import timedelta
from sqlalchemy import select
from app import models as m, schemas as s
from app.core.config import settings
from app.core.errors import AppError, require
from app.repositories import ScopedRepository
from app.services.common import dto, today, active_membership
from app.services.auth_service import AuthService
from app.domain.schedule import issues

RESOURCES = {
    "branches": (m.Branch, s.BranchInput),
    "staff": (m.Staff, s.StaffInput),
    "services": (m.Service, s.ServiceInput),
    "clients": (m.Client, s.ClientInput),
}


class WorkspaceService:
    def __init__(self, db, actor, scope_id):
        actor.manage(scope_id)
        self.db, self.actor = db, actor
        self.repo = ScopedRepository(db, actor, scope_id)

    def snapshot(self):
        r = self.repo
        data = {
            key: [dto(x) for x in r.all(model)]
            for key, model in {
                "branches": m.Branch,
                "staff": m.Staff,
                "memberships": m.Membership,
                "services": m.Service,
                "clients": m.Client,
                "visits": m.Visit,
                "duties": m.Duty,
                "windows": m.RequestWindow,
                "submissions": m.Submission,
                "pay_terms": m.PayTerm,
            }.items()
        }
        data["scope"] = dto(r.scope)
        data["company"] = dto(self.db.get(m.Company, r.scope.company_id))
        assignments, cb = r.all(m.Assignment), r.all(m.ClientBranch)
        for p in data["staff"]:
            p["branch_ids"] = sorted(
                set(
                    x["branch_id"]
                    for x in data["memberships"]
                    if x["staff_id"] == p["id"]
                    and x["valid_from"] <= today().isoformat()
                    and (
                        not x["valid_until"] or x["valid_until"] >= today().isoformat()
                    )
                )
            )
            user = self.db.get(m.User, p["user_id"]) if p["user_id"] else None
            p["login_id"], p["account_active"] = (
                (user.login_id, user.active) if user else (None, False)
            )
            p["account_role"] = user.role if user else None
        for c in data["clients"]:
            c["branch_ids"] = [x.branch_id for x in cb if x.client_id == c["id"]]
        for v in data["visits"]:
            v["staff_ids"] = [x.staff_id for x in assignments if x.visit_id == v["id"]]
        data["history"] = [
            dto(x)
            for x in self.db.scalars(
                select(m.History)
                .where(m.History.scope_id == r.scope_id)
                .order_by(m.History.created_at.desc())
                .limit(50)
            )
        ]
        data["issues"] = issues(data)
        data["geocoding_enabled"] = bool(
            settings.mapbox_token and settings.geocoding_permanent_enabled
        )
        return data

    def _safe_published(self):
        data = self.snapshot()
        protected = {
            v["id"]
            for v in data["visits"]
            if v["status"] in ("confirmed", "done") and v["date"] >= today().isoformat()
        }
        errors = [
            i
            for i in data["issues"]
            if i["level"] == "error" and protected.intersection(i["visit_ids"])
        ]
        if errors:
            raise AppError(
                409,
                "公開済みの訪問に影響します。予定を再調整してから変更してください",
                errors,
            )

    def save(self, resource, payload, id=None, *, bind_owner=False):
        require(resource in RESOURCES, "対象が見つかりません", 404)
        model, schema = RESOURCES[resource]
        data = schema.model_validate(payload)
        r = self.repo
        r.lock()
        values = data.model_dump(exclude={"expected_version", "branch_ids"})
        if bind_owner:
            require(resource == "staff" and id is None, "操作が不正です")
            self._require_unlinked_owner()
            require(data.active, "自分のスタッフ情報は有効で登録してください")
            values["user_id"] = self.actor.id
        row = r.get(model, id, lock=True) if id else None
        if row:
            r.version(row, data.expected_version)
        if row and not data.active:
            future = [
                v
                for v in r.all(m.Visit)
                if v.date >= today() and v.status != "cancelled"
            ]
            if resource == "staff":
                assigned = {
                    a.visit_id for a in r.all(m.Assignment) if a.staff_id == row.id
                }
                in_use = any(v.id in assigned for v in future)
            else:
                field = {
                    "branches": "branch_id",
                    "clients": "client_id",
                    "services": "service_id",
                }[resource]
                in_use = any(getattr(v, field) == row.id for v in future)
            require(
                not in_use,
                "今後の訪問予定が残っています。予定を変更してから無効にしてください",
                409,
            )
        if resource in ("staff", "clients"):
            require(
                len(set(data.branch_ids)) == len(data.branch_ids),
                "所属営業所が重複しています",
            )
            for bid in data.branch_ids:
                require(r.get(m.Branch, bid).active, "無効な営業所です")
        if resource == "staff":
            for service_id in data.service_ids:
                r.get(m.Service, service_id)
        address_changed = resource == "clients" and (
            not row or row.address != data.address
        )
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            row = r.add(model, **values)
        if resource == "staff":
            current = [
                x
                for x in r.all(m.Membership)
                if x.staff_id == row.id and active_membership(x, today())
            ]
            for member in current:
                if member.branch_id not in data.branch_ids:
                    future = self.db.scalar(
                        select(m.Visit.id)
                        .join(m.Assignment, m.Assignment.visit_id == m.Visit.id)
                        .where(
                            m.Visit.scope_id == r.scope_id,
                            m.Assignment.staff_id == row.id,
                            m.Visit.branch_id == member.branch_id,
                            m.Visit.date >= today(),
                            m.Visit.status != "cancelled",
                        )
                    )
                    require(
                        not future,
                        "所属を外す前に、その営業所の予定を変更してください",
                        409,
                    )
                    if member.valid_from == today():
                        self.db.delete(member)
                    else:
                        member.valid_until = today() - timedelta(days=1)
            for bid in set(data.branch_ids) - {x.branch_id for x in current}:
                r.add(m.Membership, staff_id=row.id, branch_id=bid, valid_from=today())
        if resource == "clients":
            old = [x for x in r.all(m.ClientBranch) if x.client_id == row.id]
            for x in old:
                if x.branch_id not in data.branch_ids:
                    require(
                        not any(
                            v.client_id == row.id
                            and v.branch_id == x.branch_id
                            and v.date >= today()
                            and v.status != "cancelled"
                            for v in r.all(m.Visit)
                        ),
                        "訪問予定が残る営業所を外せません",
                        409,
                    )
                    self.db.delete(x)
            for bid in set(data.branch_ids) - {x.branch_id for x in old}:
                r.add(m.ClientBranch, client_id=row.id, branch_id=bid)
            if address_changed:
                row.address_revision += 1
                row.geometry_version += 1
                row.latitude = row.longitude = None
                row.candidates, row.coordinate_source = [], ""
                row.geocode_status = "unset"
                self._queue_geocode(row)
        self.db.flush()
        self._safe_published()
        r.record(
            "update" if id else "create", row, f"{row.name}を{'更新' if id else '登録'}"
        )
        self.db.commit()
        return {"id": row.id, "version": row.version}

    def _require_unlinked_owner(self):
        require(
            self.actor.role == "owner"
            and self.repo.scope.owner_user_id == self.actor.id,
            "オーナー本人だけが設定できます",
            403,
        )
        require(
            not any(x.user_id == self.actor.id for x in self.repo.all(m.Staff)),
            "自分のスタッフ情報は登録済みです。画面を再読み込みしてください",
            409,
        )

    def link_owner_profile(self, data):
        r = self.repo
        r.lock()
        self._require_unlinked_owner()
        row = r.get(m.Staff, data.staff_id, lock=True)
        require(row.active, "有効なスタッフを選んでください")
        require(not row.user_id, "このスタッフは別のアカウントに紐付いています", 409)
        r.version(row, data.expected_version)
        row.user_id = self.actor.id
        r.record("owner_profile", row, f"{row.name}をオーナー本人に設定")
        self.db.commit()
        return {"id": row.id, "version": row.version}

    def _queue_geocode(self, row):
        if (
            not row.address
            or not settings.mapbox_token
            or not settings.geocoding_permanent_enabled
        ):
            return
        job = next(
            (
                x
                for x in self.repo.all(m.GeocodeJob)
                if x.client_id == row.id
                and x.address_revision == row.address_revision
                and x.geometry_version == row.geometry_version
            ),
            None,
        )
        if job:
            if job.status in ("queued", "running", "done"):
                return
            job.status, job.attempts, job.next_run = "queued", 0, m.utcnow()
        else:
            self.repo.add(
                m.GeocodeJob,
                client_id=row.id,
                address_revision=row.address_revision,
                geometry_version=row.geometry_version,
            )
        row.geocode_status = "queued"

    def coordinates(self, id, data):
        r = self.repo
        r.lock()
        row = r.get(m.Client, id, lock=True)
        r.version(row, data.expected_version)
        row.latitude, row.longitude = data.latitude, data.longitude
        row.geometry_version += 1
        row.geocode_status, row.coordinate_source, row.candidates = (
            "resolved",
            "manual",
            [],
        )
        r.record("coordinates", row, "訪問先の位置を手動で設定")
        self.db.commit()
        return {"ok": True}

    def geocode(self, id, data):
        r = self.repo
        r.lock()
        row = r.get(m.Client, id, lock=True)
        r.version(row, data.expected_version)
        require(
            settings.mapbox_token and settings.geocoding_permanent_enabled,
            "位置取得サービスが未設定です。緯度・経度を入力できます",
            409,
        )
        self._queue_geocode(row)
        self.db.commit()
        return {"ok": True}

    def member(self, data):
        r = self.repo
        r.lock()
        staff = r.get(m.Staff, data.staff_id)
        require(not staff.user_id, "アカウントは登録済みです", 409)
        require(
            not self.db.scalar(
                select(m.User).where(m.User.login_id == data.login_id.casefold())
            ),
            "このログインIDは使用されています",
            409,
        )
        user = m.User(name=staff.name, login_id=data.login_id.casefold(), role="member")
        self.db.add(user)
        self.db.flush()
        staff.user_id = user.id
        token = AuthService(self.db).setup_token(user)
        r.record("account", staff, "メンバーアカウントを登録")
        self.db.commit()
        return {"setup_token": token}

    def account(self, staff_id, active=None):
        r = self.repo
        r.lock()
        staff = r.get(m.Staff, staff_id)
        require(staff.user_id, "アカウントがありません", 404)
        user = self.db.get(m.User, staff.user_id)
        require(user.role == "member", "メンバー以外の変更はできません", 403)
        result = {}
        if active is not None:
            user.active = active
            user.auth_version += 1
        else:
            result["setup_token"] = AuthService(self.db).setup_token(user)
        r.record("account", staff, "アカウント設定を変更")
        self.db.commit()
        return result

    def pay(self, staff_id, data):
        r = self.repo
        r.lock()
        staff = r.get(m.Staff, staff_id)
        require(
            not any(
                x.staff_id == staff_id and x.effective_from == data.effective_from
                for x in r.all(m.PayTerm)
            ),
            "同じ適用開始日の条件が存在します",
            409,
        )
        row = r.add(m.PayTerm, staff_id=staff_id, **data.model_dump())
        r.record("pay_term", row, f"{staff.name}の雇用・費用条件を追加")
        self.db.commit()
        return dto(row)
