from sqlalchemy import select
from app import models as m
from app.core.errors import require
from app.db import context


class ScopedRepository:
    def __init__(self, db, actor, scope_id):
        self.db, self.actor, self.scope_id = db, actor, scope_id
        context(db, actor.id, actor.role, scope_id)
        self.scope = db.get(m.OwnerScope, scope_id)
        require(self.scope is not None, "対象が見つかりません", 404)
        self.keys = {"company_id": self.scope.company_id, "scope_id": scope_id}

    def all(self, model):
        context(self.db, self.actor.id, self.actor.role, self.scope_id)
        return list(
            self.db.scalars(
                select(model)
                .where(model.scope_id == self.scope_id)
                .order_by(model.created_at)
            )
        )

    def get(self, model, id, lock=False):
        context(self.db, self.actor.id, self.actor.role, self.scope_id)
        query = (
            select(model)
            .where(model.scope_id == self.scope_id, model.id == id)
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        row = self.db.scalar(query)
        require(row is not None, "対象が見つかりません", 404)
        return row

    def add(self, model, **values):
        row = model(**self.keys, **values)
        self.db.add(row)
        self.db.flush()
        return row

    def lock(self):
        context(self.db, self.actor.id, self.actor.role, self.scope_id)
        self.db.scalar(
            select(m.OwnerScope)
            .where(m.OwnerScope.id == self.scope_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def record(self, action, row, summary):
        self.scope.revision += 1
        self.add(
            m.History,
            actor_id=self.actor.id,
            action=action,
            target_id=row.id,
            summary=summary,
        )

    def version(self, row, expected):
        require(
            row.version == expected,
            "別の操作で更新されています。再読み込みしてください",
            409,
        )
        row.version += 1
