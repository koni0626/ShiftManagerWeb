from datetime import date
from sqlalchemy import select
from app import models as m
from app.core.errors import require
from app.repositories import ScopedRepository
from app.services.common import dto, today, active_membership
from app.services.availability_service import AvailabilityService


class MemberService:
    def __init__(self, db, actor):
        actor.personal_schedule()
        self.db, self.actor = db, actor
        self.repo = ScopedRepository(db, actor, actor.scope_id)

    def schedule(self):
        r, sid = self.repo, self.actor.staff_id
        publications = list(
            self.db.scalars(
                select(m.Publication).where(
                    m.Publication.scope_id == r.scope_id, m.Publication.staff_id == sid
                )
            )
        )
        memberships = [x for x in r.all(m.Membership) if x.staff_id == sid]
        visits = []
        for p in publications:
            item = dict(p.snapshot)
            v = r.get(m.Visit, p.visit_id)
            assigned = any(
                a.visit_id == v.id and a.staff_id == sid for a in r.all(m.Assignment)
            )
            allowed = (
                assigned
                and v.status != "cancelled"
                and any(
                    x.branch_id == item["branch_id"]
                    and active_membership(x, date.fromisoformat(item["date"]))
                    and active_membership(x, today())
                    for x in memberships
                )
            )
            if allowed:
                c = r.get(m.Client, item["client_id"])
                item["location"] = dto(
                    c,
                    [
                        "label",
                        "address",
                        "building",
                        "phone",
                        "guide",
                        "latitude",
                        "longitude",
                        "geocode_status",
                    ],
                )
            else:
                item.pop("client_id", None)
                item["client_label"] = "訪問予定"
            visits.append(item)
        return {
            "visits": visits,
            "duties": [
                dto(
                    x, ["id", "date", "start", "end", "off", "break_start", "break_end"]
                )
                for x in r.all(m.Duty)
                if x.staff_id == sid and x.published
            ],
            "windows": [dto(x) for x in r.all(m.RequestWindow)],
            "submissions": [
                dto(x, ["id", "version", "month", "status", "days", "reason"])
                for x in r.all(m.Submission)
                if x.staff_id == sid
            ],
            "notices": [
                dto(x, ["id", "text", "read", "created_at"])
                for x in r.all(m.Notice)
                if x.staff_id == sid
            ],
        }

    def requests(self, month, data=None, action=None, expected=None):
        return AvailabilityService(self.db, self.actor).requests(
            month, data, action, expected
        )

    def read_notice(self, id):
        row = self.repo.get(m.Notice, id)
        require(row.staff_id == self.actor.staff_id, "対象が見つかりません", 404)
        row.read = True
        self.db.commit()
        return {"ok": True}
