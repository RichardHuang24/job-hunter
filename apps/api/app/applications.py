"""Applications: tracking each one from "to apply" to an answer.

An application made from one of your jobs copies the job's title, company,
place and link, so it keeps them after the posting closes. Each change of
status is kept as an event - the application's history. Everything is per
user; the routes check ownership.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ACTIVE_STATUSES, APPLICATION_STATUSES, Application, ApplicationEvent, Job, User, UserJob
from app.schemas.applications import ApplicationCreate, ApplicationPatch
from app.sources import SOURCES

LABELS = dict(APPLICATION_STATUSES)
SENT = {"applied", "interviewing", "offer", "accepted", "rejected", "no_response"}  # these mean it was sent


class AlreadyTracked(ValueError):
    def __init__(self, application: Application):
        super().__init__("This job already has an application.")
        self.application = application


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _event(application: Application, kind: str, at: dt.datetime) -> None:
    application.events.append(ApplicationEvent(user_id=application.user_id, kind=kind, status=application.status, at=at))


def _sent_today(application: Application, now: dt.datetime) -> None:
    if application.status in SENT and application.applied_on is None:
        application.applied_on = now.date()


def create(db: Session, user: User, data: ApplicationCreate, now: dt.datetime | None = None) -> Application:
    now = now or _now()
    application = Application(user_id=user.id, status=data.status, applied_on=data.applied_on, notes=data.notes,
                              title=data.title, company=data.company, location=data.location, url=data.url,
                              created_at=now, updated_at=now)
    if data.user_job_id:
        user_job = db.get(UserJob, data.user_job_id)
        if user_job is None or user_job.user_id != user.id:
            raise LookupError("No such job.")
        existing = db.scalar(select(Application).where(Application.user_job_id == user_job.id))
        if existing is not None:
            raise AlreadyTracked(existing)
        job = user_job.job
        application.user_job_id = user_job.id
        application.title = data.title or job.title
        application.company = data.company or job.company
        application.location = data.location or job.location
        application.url = data.url or job.url
    _sent_today(application, now)
    db.add(application)
    _event(application, "created", now)
    db.flush()
    return application


def update(application: Application, data: ApplicationPatch, now: dt.datetime | None = None) -> Application:
    now = now or _now()
    changes = data.model_dump(exclude_unset=True)
    status_changed = "status" in changes and changes["status"] != application.status
    for field, value in changes.items():
        setattr(application, field, value)
    if status_changed:
        if "applied_on" not in changes:
            _sent_today(application, now)
        _event(application, "status", now)
    application.updated_at = now
    return application


def job_closed(db: Session, applications: Iterable[Application], now: dt.datetime | None = None) -> set[str]:
    """The ids of applications whose job has closed or expired."""
    now = now or _now()
    ids = [a.user_job_id for a in applications if a.user_job_id]
    if not ids:
        return set()
    rows = db.execute(select(UserJob.id, Job).join(Job, UserJob.job_id == Job.id).where(UserJob.id.in_(ids))).all()
    closed_jobs = {user_job_id for user_job_id, job in rows if job.is_closed(now)}
    return {a.id for a in applications if a.user_job_id in closed_jobs}


def read(application: Application, closed: set[str]) -> dict:
    return {
        "id": application.id, "user_job_id": application.user_job_id, "title": application.title,
        "company": application.company, "location": application.location, "url": application.url,
        "status": application.status, "applied_on": application.applied_on, "next_step": application.next_step,
        "next_step_on": application.next_step_on, "notes": application.notes, "job_closed": application.id in closed,
        "created_at": application.created_at, "updated_at": application.updated_at,
    }


def counts(db: Session, user: User) -> dict:
    by_status = dict.fromkeys(LABELS, 0)
    for status, n in db.execute(select(Application.status, func.count()).where(Application.user_id == user.id)
                                .group_by(Application.status)).all():
        by_status[status] = n
    active = sum(n for status, n in by_status.items() if status in ACTIVE_STATUSES)
    return {"active": active, "closed": sum(by_status.values()) - active, "by_status": by_status}


def tracked(db: Session, user_job_ids: list[str]) -> dict[str, dict]:
    """user_job_id -> {id, status}, for showing on jobs."""
    if not user_job_ids:
        return {}
    rows = db.execute(select(Application.user_job_id, Application.id, Application.status)
                      .where(Application.user_job_id.in_(user_job_ids))).all()
    return {user_job_id: {"id": app_id, "status": status} for user_job_id, app_id, status in rows}


# CSV


CSV_COLUMNS = ("Company", "Job title", "Location", "Status", "Applied on", "Next step", "Next step on", "Link",
               "Notes", "Found on", "Added", "Last changed")


def safe_cell(value: object) -> str:
    """A spreadsheet cell that can't run as a formula (CSV injection): text
    starting with = + - @ or a tab is prefixed with an apostrophe."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(db: Session, user: User) -> str:
    rows = db.execute(select(Application, Job.source).outerjoin(UserJob, Application.user_job_id == UserJob.id)
                      .outerjoin(Job, UserJob.job_id == Job.id).where(Application.user_id == user.id)
                      .order_by(Application.created_at.desc(), Application.id)).all()
    out = io.StringIO()
    out.write("﻿")  # so Excel reads it as UTF-8
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for application, source in rows:
        found = SOURCES[source].label if source in SOURCES else ("Added by hand" if application.user_job_id is None else "")
        writer.writerow([safe_cell(v) for v in (
            application.company, application.title, application.location, LABELS.get(application.status, application.status),
            application.applied_on.isoformat() if application.applied_on else "", application.next_step,
            application.next_step_on.isoformat() if application.next_step_on else "", application.url, application.notes,
            found, application.created_at.date().isoformat(), application.updated_at.date().isoformat())])
    return out.getvalue()
