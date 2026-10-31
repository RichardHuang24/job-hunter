"""Himalayas (himalayas.app): remote jobs at companies hiring worldwide.

Free, and no key needed; HIMALAYAS_API_KEY (free from himalayas.app) raises
the limits to 60 calls a minute and 10,000 a day. The data refreshes daily,
so answers are kept for six hours. API terms, as published at
https://himalayas.app/api - see docs/job-sources.md:

- Apply buttons use `applicationLink` unchanged.
- A visible link credits Himalayas as the source.
- Jobs are shown only on sites and apps you run, and never passed on to
  other job boards or aggregators (no feeds, no JobPosting markup).
- Jobs are taken down once they expire or close: `check()` asks Himalayas
  about each stored job daily, and expired ones are hidden.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

from app.config import get_settings
from app.countries import parse_places
from app.sources.base import Posting, Query, Source, Status
from app.sources.http import Fetcher, SourceError
from app.sources.text import html_to_text

SEARCH = "https://himalayas.app/jobs/api/search"
CHECK = "https://himalayas.app/jobs/api/companies/{company}/jobs/{slug}"
PAGE_SIZE = 20  # fixed by the API
MAX_PAGES = 2  # per term and country: the 40 most relevant
MAX_COUNTRIES = 5  # more than this: one search for anywhere, filtered here
PERIODS = {"annual": "year", "monthly": "month", "hourly": "hour"}  # weekly and fortnightly pay is left out
_JOB_PATH = re.compile(r"/companies/([^/?#]+)/jobs/([^/?#]+)")

_shared: Fetcher | None = None


def _fetcher() -> Fetcher:
    global _shared
    if _shared is None:
        _shared = Fetcher(min_interval=1.1, ttl=6 * 3600)
    return _shared


def _time(value: Any) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(int(value), dt.UTC) if value else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _number(value: Any) -> int | None:
    try:
        return round(float(value)) if value is not None and float(value) > 0 else None
    except (TypeError, ValueError):
        return None


def remote_label(names: Sequence[str], worldwide: bool) -> str:
    """'Remote (United Kingdom)', 'Remote (Germany, Spain and 3 more)'"""
    if worldwide or not names:
        return "Remote (anywhere)" if worldwide else "Remote"
    shown = ", ".join(names[:2]) if len(names) > 3 else ", ".join(names)
    return f"Remote ({shown}{f' and {len(names) - 2} more' if len(names) > 3 else ''})"


def to_posting(raw: dict[str, Any], now: dt.datetime) -> Posting | None:
    """A Himalayas job -> a Posting; None if it's unusable or has expired."""
    title = html.unescape(str(raw.get("title") or "")).strip()
    url = str(raw.get("applicationLink") or raw.get("guid") or "").strip()
    if not title or not url.startswith("https://"):
        return None
    expires = _time(raw.get("expiryDate"))
    if expires is not None and expires <= now:
        return None
    guid = str(raw.get("guid") or url)
    path = _JOB_PATH.search(guid)
    restrictions = [str(n) for n in raw.get("locationRestrictions") or [] if n]
    places = parse_places(restrictions)
    worldwide = not restrictions
    low, high = _number(raw.get("minSalary")), _number(raw.get("maxSalary"))
    currency = str(raw.get("currency") or "").upper()
    period = PERIODS.get(str(raw.get("salaryPeriod") or "annual"), "")
    if not (len(currency) == 3 and period and (low or high)):
        low = high = None
        currency = period = ""
    return Posting(
        source_id=f"{path[1]}/{path[2]}" if path else guid,
        url=url,
        title=title,
        company=html.unescape(str(raw.get("companyName") or "")).strip(),
        location=remote_label(restrictions, worldwide),
        country=places.codes[0] if len(places.codes) == 1 else "",
        arrangement="remote",
        salary_min=low, salary_max=high, salary_currency=currency, salary_period=period,
        posted_at=_time(raw.get("pubDate")),
        description=html_to_text(str(raw.get("description") or raw.get("excerpt") or "")),
        countries=places.codes,
        worldwide=worldwide,
        expires_at=expires,
    )


class HimalayasSource(Source):
    key = "himalayas"
    label = "Himalayas"
    description = "Remote jobs at companies hiring worldwide, from Himalayas. Free; updated daily."
    homepage = "https://himalayas.app"
    commercial = True  # "You may use the API in personal and commercial integrations"
    remote_only = True
    check_every = dt.timedelta(days=1)
    check_batch = 25  # one call each, at the free pace

    def __init__(self, fetcher: Fetcher | None = None, api_key: str | None = None):
        self.http = fetcher or _fetcher()
        self.api_key = get_settings().himalayas_api_key if api_key is None else api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def search(self, query: Query) -> list[Posting]:
        now = dt.datetime.now(dt.UTC)
        many = len(query.countries) > MAX_COUNTRIES
        wanted = set(query.countries)
        out: dict[str, Posting] = {}
        for country in ("",) if many or not query.countries else query.countries:
            for page in range(1, MAX_PAGES + 1):
                params: dict[str, Any] = {"q": query.term, "page": page}
                if country:
                    params["country"] = country
                data = self.http.json(SEARCH, params, self._headers())
                jobs = data.get("jobs") if isinstance(data, dict) else None
                if not isinstance(jobs, list):
                    raise SourceError("Himalayas sent an answer without jobs")
                for raw in jobs:
                    posting = to_posting(raw, now) if isinstance(raw, dict) else None
                    if posting is None or posting.source_id in out:
                        continue
                    if many and not (posting.worldwide or wanted & set(posting.countries)):
                        continue
                    out[posting.source_id] = posting
                if len(jobs) < PAGE_SIZE or len(out) >= query.limit:
                    break
            if len(out) >= query.limit:
                break
        return list(out.values())[: query.limit]

    def check(self, jobs: Sequence[tuple[str, str]]) -> dict[str, Status]:
        """200: open; 410: closed; 404: no job there any more."""
        out: dict[str, Status] = {}
        for source_id, _url in jobs:
            company, _, slug = source_id.partition("/")
            if not company or not slug or "/" in slug:
                out[source_id] = "unknown"
                continue
            try:
                response = self.http.get(CHECK.format(company=quote(company), slug=quote(slug)), headers=self._headers())
            except SourceError:
                break  # the rest wait for the next pass
            if response.status_code == 429:
                break
            out[source_id] = {200: "open", 410: "closed", 404: "closed"}.get(response.status_code, "unknown")
        return out
