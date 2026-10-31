"""Jobicy (jobicy.com): remote jobs posted in the last seven days.

Free, no key. The whole feed is read at most once an hour - a thousand or
more jobs, 100 a call - and every search is answered from that copy. API terms, as published
at https://jobicy.com/jobs-rss-feed - see docs/job-sources.md:

- Jobicy is credited as the source, with a link.
- Apply links go to the Jobicy job page (`url`), as the free API gives it.
- Commercial use, storing and caching are allowed; closed jobs are taken
  down. A job missing from the feed may still be open, so `check()` asks
  Jobicy's status endpoint, in batches of up to 100, every few hours.
"""

from __future__ import annotations

import datetime as dt
import html
import threading
import time
from collections.abc import Sequence
from typing import Any

from app.countries import parse_places
from app.sources.base import Posting, Query, Source, Status, title_has_words
from app.sources.himalayas import remote_label
from app.sources.http import Fetcher, SourceError
from app.sources.text import html_to_text

FEED = "https://jobicy.com/api/jobs"
STATUS = "https://jobicy.com/api/jobs/status"
PAGE_SIZE = 100  # the API's most
MAX_PAGES = 30  # up to 3,000 jobs a pass
SYNC_SECONDS = 3600  # Jobicy: start a sync pass at most once an hour
RETRY_SECONDS = 600  # after a failed pass
PERIODS = {"yearly": "year", "annual": "year", "monthly": "month", "daily": "day", "hourly": "hour"}
STATUSES: dict[str, Status] = {"active": "open", "closed": "closed"}


class Feed:
    """The whole Jobicy feed, read once an hour and shared by every search."""

    def __init__(self, fetcher: Fetcher):
        self.http = fetcher
        self.lock = threading.Lock()
        self.jobs: list[dict[str, Any]] = []
        self.fetched_at: float | None = None
        self.failed: tuple[float, str] | None = None

    def current(self) -> list[dict[str, Any]]:
        with self.lock:
            now = time.monotonic()
            if self.fetched_at is not None and now - self.fetched_at < SYNC_SECONDS:
                return self.jobs
            if self.failed and now - self.failed[0] < RETRY_SECONDS:
                raise SourceError(self.failed[1])
            try:
                self.jobs, self.fetched_at, self.failed = self._read(), time.monotonic(), None
            except SourceError as exc:
                self.failed = (time.monotonic(), str(exc))
                raise
            return self.jobs

    def _read(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        cursor = ""
        for _ in range(MAX_PAGES):
            data = self.http.json(FEED, {"count": PAGE_SIZE, **({"cursor": cursor} if cursor else {})})
            page = data.get("jobs") if isinstance(data, dict) else None
            if not isinstance(page, list):
                raise SourceError("Jobicy sent an answer without jobs")
            jobs.extend(job for job in page if isinstance(job, dict))
            cursor = str(data.get("nextCursor") or "")
            if not data.get("hasMore") or not cursor:
                break
        return jobs


_shared: Feed | None = None


def _feed() -> Feed:
    global _shared
    if _shared is None:
        _shared = Feed(Fetcher(min_interval=2.0))
    return _shared


def _time(value: Any) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
    return parsed.astimezone(dt.UTC) if parsed and parsed.tzinfo else parsed.replace(tzinfo=dt.UTC) if parsed else None


def _number(value: Any) -> int | None:
    try:
        return round(float(value)) if value is not None and float(value) > 0 else None
    except (TypeError, ValueError):
        return None


def to_posting(raw: dict[str, Any]) -> Posting | None:
    title = html.unescape(str(raw.get("jobTitle") or "")).strip()
    url = str(raw.get("url") or "").strip()
    if not title or not url.startswith("https://") or raw.get("id") in (None, ""):
        return None
    names = [part.strip() for part in str(raw.get("jobGeo") or "").split(",") if part.strip()]
    places = parse_places(names)
    low, high = _number(raw.get("salaryMin")), _number(raw.get("salaryMax"))
    currency = str(raw.get("salaryCurrency") or "").upper()
    period = PERIODS.get(str(raw.get("salaryPeriod") or "").lower(), "")
    if not (len(currency) == 3 and period and (low or high)):
        low = high = None
        currency = period = ""
    return Posting(
        source_id=str(raw["id"]),
        url=url,
        title=title,
        company=html.unescape(str(raw.get("companyName") or "")).strip(),
        location=remote_label(names, places.worldwide and not places.codes),
        country=places.codes[0] if len(places.codes) == 1 else "",
        arrangement="remote",
        salary_min=low, salary_max=high, salary_currency=currency, salary_period=period,
        posted_at=_time(raw.get("pubDate")),
        description=html_to_text(str(raw.get("jobDescription") or raw.get("jobExcerpt") or "")),
        countries=places.codes,
        worldwide=places.worldwide,
    )


class JobicySource(Source):
    key = "jobicy"
    label = "Jobicy"
    description = "Remote jobs posted on Jobicy in the last seven days. Free."
    homepage = "https://jobicy.com"
    commercial = True  # "Commercial use, job boards, aggregators, and redistribution are permitted"
    remote_only = True
    check_every = dt.timedelta(hours=6)
    check_batch = 300  # three calls of 100

    def __init__(self, feed: Feed | None = None):
        self.feed = feed or _feed()

    def search(self, query: Query) -> list[Posting]:
        wanted = set(query.countries)
        out = []
        for raw in self.feed.current():
            if not title_has_words(str(raw.get("jobTitle") or ""), query.term):
                continue
            posting = to_posting(raw)
            if posting is None:
                continue
            # Where it's open isn't always known; those stay in, and the permit check says so.
            if wanted and posting.countries and not posting.worldwide and not wanted & set(posting.countries):
                continue
            out.append(posting)
            if len(out) >= query.limit:
                break
        return out

    def check(self, jobs: Sequence[tuple[str, str]]) -> dict[str, Status]:
        ids = list(dict.fromkeys(source_id for source_id, _ in jobs if source_id.isdigit()))
        out: dict[str, Status] = {source_id: "unknown" for source_id, _ in jobs if not source_id.isdigit()}
        for start in range(0, len(ids), 100):
            try:
                data = self.feed.http.json(STATUS, {"ids": ",".join(ids[start:start + 100])})
            except SourceError:
                break
            for item in (data.get("jobs") if isinstance(data, dict) else None) or []:
                if isinstance(item, dict) and str(item.get("id")) in ids:
                    out[str(item["id"])] = STATUSES.get(str(item.get("status")), "unknown")
        return out
