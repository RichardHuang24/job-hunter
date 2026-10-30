"""Database models.

Auth.js owns sign-in: `users`, `accounts`, `sessions` and `verification_token`
follow the schema its Postgres adapter (@auth/pg-adapter) reads and writes -
same table and column names, quoted camelCase included - with foreign keys
and unique indexes added. Alembic creates every table, Auth.js's too, so one
migration history describes the whole database.

Everything else belongs to a user and carries `user_id`.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


UtcDateTime = DateTime(timezone=True)


# --- Auth.js (@auth/pg-adapter) ---------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    email_verified: Mapped[dt.datetime | None] = mapped_column("emailVerified", UtcDateTime, nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["Profile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    targets: Mapped[list["ProfileTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="ProfileTarget.position"
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("provider", "providerAccountId", name="uq_accounts_provider_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(255))
    provider_account_id: Mapped[str] = mapped_column("providerAccountId", String(255))
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires: Mapped[dt.datetime] = mapped_column(UtcDateTime)
    session_token: Mapped[str] = mapped_column("sessionToken", String(255), unique=True)


class VerificationToken(Base):
    __tablename__ = "verification_token"

    identifier: Mapped[str] = mapped_column(Text, primary_key=True)
    token: Mapped[str] = mapped_column(Text, primary_key=True)
    expires: Mapped[dt.datetime] = mapped_column(UtcDateTime)


# --- The product --------------------------------------------------------------------------


def _list_column() -> Mapped[list]:
    return mapped_column(JSON, default=list, server_default=text("'[]'"))


class Profile(Base):
    """Who a user is and what they're looking for. The deal-breakers here -
    locations, work arrangements, work permits, salary - become pass/fail
    checks on each job; the rest feeds matching and the CV."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    headline: Mapped[str] = mapped_column(String(255), default="")  # "Registered nurse", "Marketing manager"
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")  # in their own words
    industry: Mapped[str] = mapped_column(String(64), default="")  # a preset key, presets/industries/
    market: Mapped[str] = mapped_column(String(64), default="")  # a preset key, presets/markets/
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seniority_levels: Mapped[list[str]] = _list_column()  # the levels wanted (presets/seniority.toml); [] = any
    skills: Mapped[list[str]] = _list_column()
    languages: Mapped[list[dict]] = _list_column()  # [{"name": "Spanish", "level": "professional"}]
    locations: Mapped[list[str]] = _list_column()  # places they'd work: "Manchester", "Remote (UK)"
    work_arrangements: Mapped[list[str]] = _list_column()  # onsite / hybrid / remote; [] = any
    authorized_countries: Mapped[list[str]] = _list_column()  # ISO codes where no visa is needed
    open_to_sponsorship: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), default="", server_default="")
    salary_period: Mapped[str] = mapped_column(String(8), default="year", server_default="year")
    onboarded_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class ProfileTarget(Base):
    """A role the user is after: which job titles count as it (and which
    don't), and what to search for. Usually starts from an industry preset's
    role (presets/industries/), then the user edits it."""

    __tablename__ = "profile_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(80))
    titles: Mapped[list[str]] = _list_column()  # a job title containing one of these is this role
    exclude: Mapped[list[str]] = _list_column()  # ...unless it contains one of these
    search: Mapped[list[str]] = _list_column()  # what to type into job boards
    preset_role: Mapped[str] = mapped_column(String(130), default="", server_default="")  # "healthcare/registered-nurse"
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="targets")


TASK_STATUSES = ("queued", "running", "succeeded", "failed")


class Task(Base):
    """One unit of background work for the worker (app/worker.py): a search,
    an AI match batch, a CV build. Postgres is the queue - workers claim rows
    with SELECT ... FOR UPDATE SKIP LOCKED (app/tasks/queue.py)."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_claim", "status", "run_after"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    locked_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    locked_by: Mapped[str] = mapped_column(String(128), default="")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
