from sqlalchemy import select
from app import models as m
from app.core.errors import require
from app.services.auth_service import AuthService
from app.services.common import dto


class AdminService:
    def __init__(self, db, actor):
        actor.admin()
        self.db, self.actor = db, actor

    def overview(self):
        return {
            "companies": [dto(x) for x in self.db.scalars(select(m.Company))],
            "scopes": [dto(x) for x in self.db.scalars(select(m.OwnerScope))],
            "users": [
                dto(x, ["id", "name", "login_id", "role", "active"])
                for x in self.db.scalars(select(m.User))
            ],
        }

    def company(self, data):
        row = m.Company(**data.model_dump(exclude={"expected_version"}))
        self.db.add(row)
        self.db.commit()
        return dto(row)

    def owner(self, data):
        require(self.db.get(m.Company, data.company_id), "会社が見つかりません", 404)
        require(
            not self.db.scalar(
                select(m.User).where(m.User.login_id == data.login_id.casefold())
            ),
            "このログインIDは使用されています",
            409,
        )
        user = m.User(name=data.name, login_id=data.login_id.casefold(), role="owner")
        self.db.add(user)
        self.db.flush()
        scope = m.OwnerScope(
            company_id=data.company_id, owner_user_id=user.id, name=data.name
        )
        self.db.add(scope)
        self.db.flush()
        token = AuthService(self.db).setup_token(user)
        self.db.commit()
        return {"scope": dto(scope), "setup_token": token}
