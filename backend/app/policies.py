from dataclasses import dataclass
from app.core.errors import require


@dataclass
class Actor:
    id: str
    name: str
    role: str
    scope_id: str | None = None
    staff_id: str | None = None

    def manage(self, scope_id):
        require(
            self.role == "system_admin"
            or (self.role == "owner" and self.scope_id == scope_id),
            "この情報にはアクセスできません",
            403,
        )

    def admin(self):
        require(self.role == "system_admin", "管理者権限が必要です", 403)

    def member(self):
        require(self.role == "member" and self.staff_id, "メンバー用の操作です", 403)

    def personal_schedule(self):
        require(
            self.role in ("member", "owner") and self.staff_id,
            "自分のスタッフ情報を登録してください",
            403,
        )
