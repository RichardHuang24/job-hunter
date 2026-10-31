"""Taking down closed jobs. Some sources' terms say a job must come down once
it closes, so every RECHECK_SECONDS the worker queues a "recheck" task that
asks those sources (Source.check) about the jobs people have, oldest check
first, at most `check_batch` per source per pass."""

from __future__ import annotations

import datetime as dt
import logging
from collections import Counter

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.db.models import Job, Task, UserJob
from app.sources import Source, enabled_sources
from app.tasks import queue

log = logging.getLogger("job_hunter.recheck")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def queue_recheck(db: Session) -> bool:
    """Queues a recheck unless one is waiting or running. Commits."""
    if not any(source.check_every for source in enabled_sources()):
        return False
    pending = db.scalar(select(Task.id).where(Task.kind == "recheck", Task.status.in_(("queued", "running"))).limit(1))
    if pending is not None:
        return False
    queue.enqueue(db, "recheck", {}, max_attempts=1)
    db.commit()
    return True


def recheck_due(db: Session, sources: list[Source] | None = None, now: dt.datetime | None = None) -> dict:
    """Asks each source about its jobs that are due a check. Commits.
    {source: {"open": n, "closed": n, "unknown": n}}"""
    now = now or _now()
    result: dict[str, dict] = {}
    for source in enabled_sources() if sources is None else sources:
        if source.check_every is None:
            continue
        due = db.scalars(
            select(Job)
            .where(Job.source == source.key, Job.closed_at.is_(None),
                   or_(Job.expires_at.is_(None), Job.expires_at > now),
                   or_(Job.checked_at.is_(None), Job.checked_at <= now - source.check_every),
                   exists().where(UserJob.job_id == Job.id))
            .order_by(Job.checked_at.asc().nulls_first(), Job.id)
            .limit(source.check_batch)
        ).all()
        if not due:
            continue
        try:
            statuses = source.check([(job.source_id, job.url) for job in due])
        except Exception as exc:  # noqa: BLE001 - one source failing doesn't stop the others
            log.warning("Couldn't check %s jobs: %s", source.key, exc)
            result[source.key] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            continue
        counts: Counter[str] = Counter()
        for job in due:
            status = statuses.get(job.source_id)
            if status is None:
                continue  # not reached this time
            job.checked_at = now
            if status == "closed":
                job.closed_at = now
            counts[status] += 1
        result[source.key] = dict(counts)
    db.commit()
    return result
