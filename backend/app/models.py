import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Row:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Company(Row, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(100))
    contact: Mapped[str] = mapped_column(default="")
    active: Mapped[bool] = mapped_column(default=True)


class User(Row, Base):
    __tablename__ = "users"
    login_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str | None]
    active: Mapped[bool] = mapped_column(default=True)
    auth_version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (CheckConstraint("role IN ('system_admin','owner','member')"),)


class OwnerScope(Row, Base):
    __tablename__ = "owner_scopes"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    travel_minutes: Mapped[int] = mapped_column(default=15)
    revision: Mapped[int] = mapped_column(default=0)
    __table_args__ = (
        UniqueConstraint("company_id", "id"),
        CheckConstraint("travel_minutes >= 0"),
    )


class AuthSession(Row, Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    auth_version: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SetupToken(Row, Base):
    __tablename__ = "setup_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(default=False)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Scoped(Row):
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    scope_id: Mapped[str] = mapped_column(String(36), index=True)


def scoped_constraints(*extra):
    return (
        UniqueConstraint("company_id", "scope_id", "id"),
        ForeignKeyConstraint(
            ["company_id", "scope_id"], ["owner_scopes.company_id", "owner_scopes.id"]
        ),
        *extra,
    )


def ref(table, local):
    return ForeignKeyConstraint(
        ["company_id", "scope_id", local],
        [f"{table}.company_id", f"{table}.scope_id", f"{table}.id"],
    )


class Branch(Scoped, Base):
    __tablename__ = "branches"
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(default="")
    phone: Mapped[str] = mapped_column(default="")
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = scoped_constraints()


class Staff(Scoped, Base):
    __tablename__ = "staff"
    name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), unique=True)
    job: Mapped[str] = mapped_column(default="ヘルパー")
    qualifications: Mapped[list] = mapped_column(JSONB, default=list)
    service_ids: Mapped[list] = mapped_column(JSONB, default=list)
    weekdays: Mapped[list] = mapped_column(JSONB, default=lambda: [0, 1, 2, 3, 4])
    start: Mapped[time] = mapped_column(Time, default=time(9))
    end: Mapped[time] = mapped_column(Time, default=time(18))
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)
    max_visits: Mapped[int] = mapped_column(default=8)
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = scoped_constraints(
        CheckConstraint('"start" < "end"'), CheckConstraint("max_visits >= 0")
    )


class Membership(Scoped, Base):
    __tablename__ = "memberships"
    staff_id: Mapped[str] = mapped_column(String(36))
    branch_id: Mapped[str] = mapped_column(String(36))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    __table_args__ = scoped_constraints(
        ref("staff", "staff_id"),
        ref("branches", "branch_id"),
        CheckConstraint("valid_until IS NULL OR valid_until >= valid_from"),
    )


class Service(Scoped, Base):
    __tablename__ = "services"
    name: Mapped[str] = mapped_column(String(100))
    duration: Mapped[int] = mapped_column(default=60)
    people: Mapped[int] = mapped_column(default=1)
    jobs: Mapped[list] = mapped_column(JSONB, default=lambda: ["ヘルパー"])
    qualifications: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = scoped_constraints(CheckConstraint("duration > 0 AND people > 0"))


class Client(Scoped, Base):
    __tablename__ = "clients"
    name: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(default="")
    building: Mapped[str] = mapped_column(default="")
    phone: Mapped[str] = mapped_column(default="")
    guide: Mapped[str] = mapped_column(default="")
    private_note: Mapped[str] = mapped_column(default="")
    weekdays: Mapped[list] = mapped_column(JSONB, default=lambda: list(range(7)))
    start: Mapped[time] = mapped_column(Time, default=time(8))
    end: Mapped[time] = mapped_column(Time, default=time(20))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    address_revision: Mapped[int] = mapped_column(default=1)
    geometry_version: Mapped[int] = mapped_column(default=1)
    geocode_status: Mapped[str] = mapped_column(default="unset")
    coordinate_source: Mapped[str] = mapped_column(default="")
    candidates: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = scoped_constraints(
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)"),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180"
        ),
        CheckConstraint('"start" < "end"'),
    )


class ClientBranch(Scoped, Base):
    __tablename__ = "client_branches"
    client_id: Mapped[str] = mapped_column(String(36))
    branch_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = scoped_constraints(
        ref("clients", "client_id"),
        ref("branches", "branch_id"),
        UniqueConstraint("client_id", "branch_id"),
    )


class Visit(Scoped, Base):
    __tablename__ = "visits"
    branch_id: Mapped[str] = mapped_column(String(36))
    client_id: Mapped[str] = mapped_column(String(36))
    service_id: Mapped[str] = mapped_column(String(36))
    date: Mapped[date] = mapped_column(Date, index=True)
    start: Mapped[time] = mapped_column(Time)
    duration: Mapped[int]
    people: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(default="draft")
    note: Mapped[str] = mapped_column(default="")
    occurrence_key: Mapped[str | None] = mapped_column(unique=True)
    __table_args__ = scoped_constraints(
        ref("branches", "branch_id"),
        ref("clients", "client_id"),
        ref("services", "service_id"),
        CheckConstraint("status IN ('draft','confirmed','done','cancelled')"),
        CheckConstraint("duration > 0 AND duration <= 720 AND people > 0"),
    )


class Assignment(Scoped, Base):
    __tablename__ = "assignments"
    visit_id: Mapped[str] = mapped_column(String(36))
    staff_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = scoped_constraints(
        ref("visits", "visit_id"),
        ref("staff", "staff_id"),
        UniqueConstraint("visit_id", "staff_id"),
    )


class Publication(Scoped, Base):
    __tablename__ = "publications"
    visit_id: Mapped[str] = mapped_column(String(36))
    staff_id: Mapped[str] = mapped_column(String(36))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = scoped_constraints(
        ref("visits", "visit_id"),
        ref("staff", "staff_id"),
        UniqueConstraint("visit_id", "staff_id"),
    )


class Duty(Scoped, Base):
    __tablename__ = "duties"
    staff_id: Mapped[str] = mapped_column(String(36))
    date: Mapped[date] = mapped_column(Date)
    off: Mapped[bool] = mapped_column(default=False)
    start: Mapped[time] = mapped_column(Time)
    end: Mapped[time] = mapped_column(Time)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)
    published: Mapped[bool] = mapped_column(default=False)
    __table_args__ = scoped_constraints(
        ref("staff", "staff_id"),
        UniqueConstraint("staff_id", "date"),
        CheckConstraint('"start" < "end"'),
    )


class RequestWindow(Scoped, Base):
    __tablename__ = "request_windows"
    month: Mapped[str] = mapped_column(String(7))
    deadline: Mapped[date] = mapped_column(Date)
    __table_args__ = scoped_constraints(UniqueConstraint("scope_id", "month"))


class Submission(Scoped, Base):
    __tablename__ = "submissions"
    staff_id: Mapped[str] = mapped_column(String(36))
    month: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(default="draft")
    days: Mapped[list] = mapped_column(JSONB, default=list)
    reason: Mapped[str] = mapped_column(default="")
    __table_args__ = scoped_constraints(
        ref("staff", "staff_id"),
        UniqueConstraint("staff_id", "month"),
        CheckConstraint("status IN ('draft','submitted','returned')"),
    )


class Notice(Scoped, Base):
    __tablename__ = "notices"
    staff_id: Mapped[str] = mapped_column(String(36))
    text: Mapped[str]
    read: Mapped[bool] = mapped_column(default=False)
    __table_args__ = scoped_constraints(ref("staff", "staff_id"))


class History(Scoped, Base):
    __tablename__ = "history"
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str]
    target_id: Mapped[str]
    summary: Mapped[str]
    __table_args__ = scoped_constraints()


class PayTerm(Scoped, Base):
    __tablename__ = "pay_terms"
    staff_id: Mapped[str] = mapped_column(String(36))
    effective_from: Mapped[date] = mapped_column(Date)
    employment: Mapped[str]
    basis: Mapped[str]
    amount: Mapped[int]
    __table_args__ = scoped_constraints(
        ref("staff", "staff_id"),
        UniqueConstraint("staff_id", "effective_from"),
        CheckConstraint("basis IN ('unset','hourly','monthly') AND amount >= 0"),
    )


class GeocodeJob(Scoped, Base):
    __tablename__ = "geocode_jobs"
    client_id: Mapped[str] = mapped_column(String(36))
    address_revision: Mapped[int]
    geometry_version: Mapped[int]
    status: Mapped[str] = mapped_column(default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[str | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = scoped_constraints(
        ref("clients", "client_id"),
        UniqueConstraint("client_id", "address_revision", "geometry_version"),
    )
