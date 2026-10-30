"""The background task queue, on Postgres - no Redis to run.

A worker claims the oldest due task with SELECT ... FOR UPDATE SKIP LOCKED,
so any number of workers can share the queue without taking the same task.
A task left "running" past its lease (a worker that died) is claimed again.
A failed task is retried with a growing delay until it has used its attempts.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import Task


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def enqueue(session: Session, kind: str, payload: dict[str, Any] | None = None, *, user_id: int | None = None,
            max_attempts: int = 3, run_after: dt.datetime | None = None) -> Task:
    task = Task(kind=kind, payload=payload or {}, user_id=user_id, max_attempts=max_attempts, run_after=run_after or _now())
    session.add(task)
    session.flush()
    return task


def claim(session: Session, worker: str, lease_seconds: int, now: dt.datetime | None = None) -> Task | None:
    """The next due task, marked running for `worker` - or None. Commits."""
    now = now or _now()
    stale = now - dt.timedelta(seconds=lease_seconds)
    query = (
        select(Task)
        .where(
            or_(
                and_(Task.status == "queued", Task.run_after <= now),
                and_(Task.status == "running", Task.locked_at < stale),
            )
        )
        .order_by(Task.run_after, Task.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = session.execute(query).scalar_one_or_none()
    if task is None:
        session.rollback()
        return None
    task.status, task.locked_at, task.locked_by = "running", now, worker
    task.attempts += 1
    session.commit()
    return task


def succeed(session: Session, task: Task, result: dict[str, Any] | None = None) -> None:
    task.status, task.result, task.error, task.finished_at = "succeeded", result or {}, "", _now()
    session.commit()


def fail(session: Session, task: Task, error: str, now: dt.datetime | None = None) -> None:
    """Back in the queue after 30 s, 2 min, 8 min... - or failed for good."""
    now = now or _now()
    task.error = error[:2000]
    task.locked_at, task.locked_by = None, ""
    if task.attempts >= task.max_attempts:
        task.status, task.finished_at = "failed", now
    else:
        task.status = "queued"
        task.run_after = now + dt.timedelta(seconds=30 * 4 ** (task.attempts - 1))
    session.commit()
