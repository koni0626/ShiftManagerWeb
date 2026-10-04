from app import models as m
from app.core.errors import require
from app.services.common import dto
from app.services.workspace_service import WorkspaceService


class RequestService(WorkspaceService):
    def window(self, data):
        r = self.repo
        r.lock()
        row = next((x for x in r.all(m.RequestWindow) if x.month == data.month), None)
        if row:
            row.deadline, row.version = data.deadline, row.version + 1
        else:
            row = r.add(m.RequestWindow, **data.model_dump())
        r.record("request_window", row, f"{data.month}の勤務希望の募集を設定")
        self.db.commit()
        return dto(row)

    def return_submission(self, id, data):
        r = self.repo
        r.lock()
        row = r.get(m.Submission, id)
        r.version(row, data.expected_version)
        require(row.status == "submitted", "提出済みの勤務希望ではありません", 409)
        row.status, row.reason = "returned", data.reason
        r.add(
            m.Notice,
            staff_id=row.staff_id,
            text=f"{row.month}の勤務希望が差し戻されました：{data.reason}",
        )
        r.record("return_request", row, "勤務希望を差し戻し")
        self.db.commit()
        return dto(row)
