from app import models as m
from app.core.errors import require
from app.repositories import ScopedRepository
from app.services.common import dto, today


class AvailabilityService:
    """勤務希望の本人入力と代理入力で提出・期限・排他制御を共有する。"""

    def __init__(self, db, actor, scope_id=None, staff_id=None):
        if staff_id is None:
            actor.personal_schedule()
            scope_id, staff_id = actor.scope_id, actor.staff_id
        else:
            actor.manage(scope_id)
        self.db, self.actor, self.staff_id = db, actor, staff_id
        self.repo = ScopedRepository(db, actor, scope_id)

    def requests(self, month, data=None, action=None, expected=None):
        r, sid = self.repo, self.staff_id
        r.lock()
        staff = r.get(m.Staff, sid)
        require(staff.active, "無効なスタッフの勤務希望は入力できません", 409)
        window = next((x for x in r.all(m.RequestWindow) if x.month == month), None)
        require(window, "この月の勤務希望は募集されていません", 404)
        row = next(
            (x for x in r.all(m.Submission) if x.month == month and x.staff_id == sid),
            None,
        )
        require(
            window.deadline >= today()
            or (row and row.status == "returned" and action != "withdraw"),
            "提出期限を過ぎています",
            409,
        )
        if data:
            require(
                not row or row.status != "submitted",
                "提出を取り下げてから編集してください",
                409,
            )
            require(
                all(x.date.strftime("%Y-%m") == month for x in data.days),
                "対象月以外の日付があります",
            )
            require(
                len(set(x.date for x in data.days)) == len(data.days),
                "日付が重複しています",
            )
            if row:
                r.version(row, data.expected_version)
            else:
                require(
                    data.expected_version is None,
                    "勤務希望を再読み込みしてください",
                    409,
                )
                row = r.add(m.Submission, staff_id=sid, month=month)
            row.days = [x.model_dump(mode="json") for x in data.days]
        else:
            require(row, "勤務希望を入力してください")
            r.version(row, expected)
            if action == "submit":
                require(
                    row.status in ("draft", "returned") and row.days,
                    "提出する勤務希望を入力してください",
                    409,
                )
                row.status = "submitted"
            elif action == "withdraw":
                require(
                    row.status == "submitted", "提出済みの勤務希望ではありません", 409
                )
                row.status = "draft"
            else:
                require(False, "操作が不正です")
        proxy = sid != self.actor.staff_id
        verb = {"submit": "提出", "withdraw": "取り下げ"}.get(action, "保存")
        r.record(
            "request_proxy" if proxy else "request",
            row,
            f"{staff.name}の{month}の勤務希望を{'代理で' if proxy else ''}{verb}",
        )
        if proxy and action == "submit":
            r.add(
                m.Notice,
                staff_id=sid,
                text=f"{month}の勤務希望が管理者により代理提出されました",
            )
        self.db.commit()
        return dto(row, ["id", "version", "month", "status", "days", "reason"])
