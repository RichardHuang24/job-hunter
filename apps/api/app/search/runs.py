"""Starting runs, and doing one on the worker.

A run asks every enabled source for every query of the saved search, stores
the postings in the shared job store, and gives the user a view of each new
one (role, level, deal-breaker checks). Jobs they already have are re-judged
but keep their saved or hidden state.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, SavedSearch, SearchRun, User, UserJob
from app.presets import get_catalog
from app.search import store
from app.search.matching import Matcher
from app.scoring.service import queue_after_run
from app.search.queries import build_queries
from app.sources import Source, enabled_sources
from app.tasks import queue

log = logging.getLogger("job_hunter.search")

ACTIVE = ("queued", "running")
MAX_SEARCHES = 5


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def active_run(db: Session, search: SavedSearch) -> SearchRun | None:
    return db.scalar(select(SearchRun).where(SearchRun.search_id == search.id, SearchRun.status.in_(ACTIVE)).limit(1))


def start_run(db: Session, search: SavedSearch, trigger: str) -> SearchRun:
    """Queues a run for the worker. The caller checks there's no active one."""
    run = SearchRun(user_id=search.user_id, search_id=search.id, trigger=trigger, status="queued", counts={}, errors=[])
    db.add(run)
    db.flush()
    task = queue.enqueue(db, "search", {"run_id": run.id}, user_id=search.user_id, max_attempts=1)
    run.task_id = task.id
    return run


def suggestion(user: User) -> dict:
    """A saved search made from the profile: the target roles' search terms,
    the profile's places, and the market's countries."""
    catalog = get_catalog()
    profile = user.profile
    terms: list[str] = []
    for target in user.targets:
        for term in target.search or [target.label]:
            if term.casefold() not in {t.casefold() for t in terms}:
                terms.append(term)
    locations = list(profile.locations) if profile else []
    market = catalog.markets.get(profile.market) if profile else None
    countries = list(market.countries) if market and 0 < len(market.countries) <= 5 else []
    if not countries and profile:
        countries = list(profile.authorized_countries[:5])
    arrangements = profile.work_arrangements if profile else []
    remote = any(place.lower().startswith("remote") for place in locations) or arrangements == ["remote"]
    return {
        "name": "From your profile", "terms": terms[:10], "locations": locations[:10], "countries": countries,
        "include_remote": remote, "sources": [], "daily": True,
    }


def _sources_for(search: SavedSearch, available: list[Source]) -> list[Source]:
    return [s for s in available if not search.sources or s.key in search.sources]


def run_search(db: Session, run: SearchRun, sources: list[Source] | None = None, now: dt.datetime | None = None) -> dict:
    now = now or _now()
    search = db.get(SavedSearch, run.search_id)
    user = db.get(User, run.user_id)
    queries, truncated = build_queries(search.terms, search.locations, search.countries, search.include_remote)
    errors: list[dict] = []
    found: dict[tuple[str, str], tuple[str, object]] = {}
    by_source: Counter[str] = Counter()

    for source in _sources_for(search, sources if sources is not None else enabled_sources()):
        for query in queries:
            if not source.covers(query):
                continue
            try:
                postings = source.search(query)
            except Exception as exc:  # noqa: BLE001 - one source failing doesn't stop the others
                log.warning("Source %s failed on %r: %s", source.key, query.term, exc)
                errors.append({"source": source.key, "message": f"{type(exc).__name__}: {exc}"[:300]})
                break
            for posting in postings:
                if (source.key, posting.source_id) not in found:
                    found[(source.key, posting.source_id)] = (source.key, posting)
                    by_source[source.key] += 1

    jobs = [store.upsert(db, key, posting, now) for key, posting in found.values()]
    db.flush()

    matcher = Matcher(user)
    have = {uj.job_id: uj for uj in db.scalars(select(UserJob).where(UserJob.user_id == user.id))}
    seen_prints = {job.fingerprint for job in db.scalars(
        select(Job).join(UserJob, UserJob.job_id == Job.id).where(UserJob.user_id == user.id))}
    new = 0
    fresh: list[UserJob] = []
    verdicts: Counter[str] = Counter()
    for job in jobs:
        user_job = have.get(job.id)
        if user_job is None:
            if job.fingerprint in seen_prints:
                continue  # the same job from another source - they have it already
            user_job = UserJob(user_id=user.id, job_id=job.id, state="new", first_run_id=run.id, first_seen_at=now)
            db.add(user_job)
            have[job.id] = user_job
            seen_prints.add(job.fingerprint)
            fresh.append(user_job)
            new += 1
        user_job.last_seen_at = now
        matcher.apply(user_job, job, now)
        verdicts[user_job.verdict] += 1

    search.last_run_at = now
    db.flush()
    scoring = queue_after_run(db, user, fresh)
    return {
        "queries": len(queries), "truncated": truncated, "found": len(found), "new": new,
        "matches": verdicts["match"], "flagged": verdicts["flagged"], "filtered": verdicts["filtered"],
        "scoring": scoring, "by_source": dict(by_source), "errors": errors,
    }


def run_task(db: Session, run_id: str) -> dict:
    """The worker's "search" task (app/tasks/handlers.py)."""
    run = db.get(SearchRun, run_id)
    if run is None:
        raise LookupError(f"No search run {run_id}")
    run.status, run.started_at = "running", _now()
    db.commit()
    try:
        counts = run_search(db, run)
    except Exception as exc:
        db.rollback()
        run = db.get(SearchRun, run_id)
        run.status, run.finished_at = "failed", _now()
        run.errors = [{"source": "", "message": f"{type(exc).__name__}: {exc}"[:300]}]
        db.commit()
        raise
    run.errors = counts.pop("errors")
    run.counts = counts
    run.status, run.finished_at = "succeeded", _now()
    db.commit()
    return {"run_id": run_id, **counts}

