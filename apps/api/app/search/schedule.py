"""Daily saved searches: the worker calls schedule_due() every minute or so
(SCHEDULE_SECONDS). SKIP LOCKED keeps two workers from queueing the same
search twice."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SavedSearch
from app.search.runs import active_run, start_run

EVERY = dt.timedelta(days=1)


def schedule_due(db: Session, now: dt.datetime | None = None, limit: int = 50) -> int:
    """Queues a run for every daily search that's due. Commits. How many were queued."""
    now = now or dt.datetime.now(dt.UTC)
    due = db.scalars(
        select(SavedSearch)
        .where(SavedSearch.daily.is_(True), SavedSearch.next_run_at.is_not(None), SavedSearch.next_run_at <= now)
        .order_by(SavedSearch.next_run_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    queued = 0
    for search in due:
        if active_run(db, search) is None:
            start_run(db, search, trigger="schedule")
            queued += 1
        search.next_run_at = now + EVERY
    db.commit()
    return queued
