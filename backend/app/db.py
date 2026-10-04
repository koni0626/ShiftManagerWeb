from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def context(db, user_id="", role="", scope_id=""):
    for key, value in {"user_id": user_id, "role": role, "scope_id": scope_id}.items():
        db.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": f"app.{key}", "value": value or ""},
        )


def get_db():
    with SessionLocal() as db:
        yield db
