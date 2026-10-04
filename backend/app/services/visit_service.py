from sqlalchemy import delete
from app import models as m, schemas as s
from app.core.errors import require, AppError
from app.services.common import dto
from app.services.workspace_service import WorkspaceService


class VisitService(WorkspaceService):
    def save_visit(self, data, id=None):
        r = self.repo
        r.lock()
        visit = r.get(m.Visit, id) if id else None
        if visit:
            require(
                visit.status == "draft",
                "確定済みの予定は再調整へ戻してから変更してください",
                409,
            )
            r.version(visit, data.expected_version)
        r.get(m.Branch, data.branch_id)
        r.get(m.Service, data.service_id)
        r.get(m.Client, data.client_id)
        require(
            any(
                x.client_id == data.client_id and x.branch_id == data.branch_id
                for x in r.all(m.ClientBranch)
            ),
            "この営業所は利用者の訪問可能営業所ではありません",
        )
        for sid in data.staff_ids:
            r.get(m.Staff, sid)
            require(
                any(
                    x.staff_id == sid
                    and x.branch_id == data.branch_id
                    and x.valid_from <= data.date
                    and (x.valid_until is None or x.valid_until >= data.date)
                    for x in r.all(m.Membership)
                ),
                "担当者は訪問日の営業所に所属していません",
            )
        values = data.model_dump(exclude={"staff_ids", "expected_version"})
        if not visit:
            visit = r.add(m.Visit, **values)
        else:
            for key, value in values.items():
                setattr(visit, key, value)
        self.db.execute(
            delete(m.Assignment).where(
                m.Assignment.scope_id == r.scope_id, m.Assignment.visit_id == visit.id
            )
        )
        for sid in data.staff_ids:
            r.add(m.Assignment, visit_id=visit.id, staff_id=sid)
        r.record("visit", visit, "訪問予定を保存")
        self.db.commit()
        return {"id": visit.id, "version": visit.version}

    def position(self, id, data):
        r = self.repo
        r.lock()
        visit = r.get(m.Visit, id)
        staff_ids = [a.staff_id for a in r.all(m.Assignment) if a.visit_id == id]
        if data.source_staff_id:
            require(data.source_staff_id in staff_ids, "担当者が変更されています", 409)
            staff_ids.remove(data.source_staff_id)
        if data.target_staff_id:
            require(data.target_staff_id not in staff_ids, "担当者が重複します")
            staff_ids.append(data.target_staff_id)
        values = dto(
            visit,
            [
                "branch_id",
                "client_id",
                "service_id",
                "date",
                "start",
                "duration",
                "people",
                "note",
            ],
        )
        values.update(
            date=data.target_date,
            start=data.target_start or visit.start,
            staff_ids=staff_ids,
            expected_version=data.expected_version,
        )
        return self.save_visit(s.VisitInput.model_validate(values), id)

    def transition(self, id, action, version):
        r = self.repo
        r.lock()
        visit = r.get(m.Visit, id)
        r.version(visit, version)
        valid = {
            "confirm": ("draft",),
            "reopen": ("confirmed",),
            "complete": ("confirmed",),
            "cancel": ("draft", "confirmed"),
        }
        require(
            action in valid and visit.status in valid[action],
            "この状態からは変更できません",
            409,
        )
        if action in ("confirm", "complete"):
            data = self.snapshot()
            errors = [
                i
                for i in data["issues"]
                if id in i["visit_ids"] and i["level"] == "error"
            ]
            if errors:
                raise AppError(422, "確認事項を解消してから確定してください", errors)
        visit.status = {
            "confirm": "confirmed",
            "reopen": "draft",
            "complete": "done",
            "cancel": "cancelled",
        }[action]
        publications = [x for x in r.all(m.Publication) if x.visit_id == id]
        assignees = [a.staff_id for a in r.all(m.Assignment) if a.visit_id == id]
        if action in ("confirm", "complete"):
            c, service, branch = (
                r.get(m.Client, visit.client_id),
                r.get(m.Service, visit.service_id),
                r.get(m.Branch, visit.branch_id),
            )
            snapshot = {
                **dto(
                    visit,
                    [
                        "id",
                        "date",
                        "start",
                        "duration",
                        "status",
                        "branch_id",
                        "client_id",
                    ],
                ),
                "client_label": c.label,
                "service_name": service.name,
                "branch_name": branch.name,
            }
            for p in publications:
                self.db.delete(p)
                if p.staff_id not in assignees:
                    r.add(
                        m.Notice,
                        staff_id=p.staff_id,
                        text="担当していた訪問の割当が変更されました",
                    )
            self.db.flush()
            for sid in assignees:
                r.add(m.Publication, visit_id=id, staff_id=sid, snapshot=snapshot)
                staff = r.get(m.Staff, sid)
                duty = next(
                    (
                        x
                        for x in r.all(m.Duty)
                        if x.staff_id == sid and x.date == visit.date
                    ),
                    None,
                )
                if not duty:
                    duty = r.add(
                        m.Duty,
                        staff_id=sid,
                        date=visit.date,
                        start=staff.start,
                        end=staff.end,
                        break_start=staff.break_start,
                        break_end=staff.break_end,
                    )
                duty.published = True
                r.add(
                    m.Notice,
                    staff_id=sid,
                    text=f"{visit.date}の予定が{'確定' if action == 'confirm' else '完了'}しました",
                )
        else:
            for p in publications:
                p.snapshot = {
                    **p.snapshot,
                    "status": "readjusting" if action == "reopen" else "cancelled",
                }
                r.add(
                    m.Notice,
                    staff_id=p.staff_id,
                    text=f"{p.snapshot['date']}の予定が{'再調整中になりました' if action == 'reopen' else '中止されました'}",
                )
        r.record(action, visit, "訪問の状態を変更")
        self.db.commit()
        return {"id": id, "version": visit.version}
