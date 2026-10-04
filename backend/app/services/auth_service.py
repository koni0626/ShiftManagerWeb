import hashlib
import secrets
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from app import models as m
from app.core.config import settings
from app.core.errors import require
from app.db import context
from app.policies import Actor

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verify(encoded, password):
    try:
        return hasher.verify(encoded or dummy_hash, password)
    except VerificationError:
        return False


class AuthService:
    def __init__(self, db):
        self.db = db

    def login(self, login_id, password, ip):
        for key, limit in (
            (digest(f"login:{login_id.casefold()}:{ip}"), 10),
            (digest(f"ip:{ip}"), 60),
        ):
            self.db.execute(
                insert(m.LoginAttempt)
                .values(key=key, count=0, window_start=m.utcnow())
                .on_conflict_do_nothing()
            )
            attempt = self.db.scalar(
                select(m.LoginAttempt)
                .where(m.LoginAttempt.key == key)
                .with_for_update()
            )
            if m.utcnow() - attempt.window_start > timedelta(minutes=15):
                attempt.count, attempt.window_start = 0, m.utcnow()
            require(
                attempt.count < limit, "試行回数が多いため、15分後にお試しください", 429
            )
            attempt.count += 1
        self.db.commit()
        user = self.db.scalar(
            select(m.User).where(m.User.login_id == login_id.casefold())
        )
        valid = verify(user.password_hash if user else None, password)
        require(
            valid and user and user.active and user.password_hash,
            "ログインIDまたはパスワードを確認してください",
            401,
        )
        actor = self.actor(user)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.db.add(
            m.AuthSession(
                token_hash=digest(token),
                csrf_hash=digest(csrf),
                user_id=user.id,
                auth_version=user.auth_version,
                expires_at=m.utcnow() + timedelta(hours=settings.session_hours),
            )
        )
        self.db.commit()
        return actor, token, csrf

    def actor(self, user):
        context(self.db, user.id, user.role)
        if user.role == "system_admin":
            return Actor(user.id, user.name, user.role)
        if user.role == "owner":
            scope = self.db.scalar(
                select(m.OwnerScope).where(m.OwnerScope.owner_user_id == user.id)
            )
            staff = self.db.scalar(
                select(m.Staff).where(
                    m.Staff.user_id == user.id,
                    m.Staff.scope_id == scope.id if scope else False,
                    m.Staff.active.is_(True),
                )
            )
        else:
            staff = self.db.scalar(select(m.Staff).where(m.Staff.user_id == user.id))
            require(
                staff is not None and staff.active, "アカウントを利用できません", 403
            )
            scope = self.db.get(m.OwnerScope, staff.scope_id)
        require(
            scope and self.db.get(m.Company, scope.company_id).active,
            "アカウントを利用できません",
            403,
        )
        context(self.db, user.id, user.role, scope.id)
        return Actor(
            user.id, user.name, user.role, scope.id, staff.id if staff else None
        )

    def authenticate(self, token, csrf=None, write=False):
        session = self.db.scalar(
            select(m.AuthSession).where(m.AuthSession.token_hash == digest(token or ""))
        )
        require(
            session and session.expires_at > m.utcnow(), "ログインしてください", 401
        )
        user = self.db.get(m.User, session.user_id)
        require(
            user.active and session.auth_version == user.auth_version,
            "再度ログインしてください",
            401,
        )
        if write:
            require(
                csrf and secrets.compare_digest(session.csrf_hash, digest(csrf)),
                "画面を再読み込みしてください",
                403,
            )
        return self.actor(user)

    def logout(self, token):
        self.db.execute(
            delete(m.AuthSession).where(m.AuthSession.token_hash == digest(token or ""))
        )
        self.db.commit()

    def setup_token(self, user):
        self.db.execute(delete(m.SetupToken).where(m.SetupToken.user_id == user.id))
        token = secrets.token_urlsafe(32)
        self.db.add(
            m.SetupToken(
                user_id=user.id,
                token_hash=digest(token),
                expires_at=m.utcnow() + timedelta(hours=24),
            )
        )
        return token

    def setup(self, token, password):
        row = self.db.scalar(
            select(m.SetupToken)
            .where(m.SetupToken.token_hash == digest(token))
            .with_for_update()
        )
        require(
            row and not row.consumed and row.expires_at > m.utcnow(),
            "設定リンクが無効または期限切れです",
            422,
        )
        user = self.db.get(m.User, row.user_id)
        require(user.active, "アカウントを利用できません", 403)
        user.password_hash, row.consumed = hasher.hash(password), True
        user.auth_version += 1
        self.db.commit()

    def password(self, actor, old, new):
        user = self.db.get(m.User, actor.id)
        require(verify(user.password_hash, old), "現在のパスワードを確認してください")
        user.password_hash = hasher.hash(new)
        user.auth_version += 1
        self.db.commit()
