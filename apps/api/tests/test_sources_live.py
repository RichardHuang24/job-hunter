"""The real Himalayas and Jobicy APIs - a handful of calls. Skipped unless
RUN_LIVE_SOURCES=1:

    RUN_LIVE_SOURCES=1 .venv/bin/pytest tests/test_sources_live.py -s
"""

from __future__ import annotations

import os

import pytest

from app.sources.base import Query
from app.sources.himalayas import HimalayasSource
from app.sources.http import Fetcher
from app.sources.jobicy import Feed, JobicySource, to_posting

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE_SOURCES") != "1", reason="set RUN_LIVE_SOURCES=1 to call the real APIs")


def test_himalayas():
    source = HimalayasSource(Fetcher(min_interval=1.1), api_key=os.environ.get("HIMALAYAS_API_KEY", ""))
    found = source.search(Query("data scientist", countries=("GB",), remote=True, limit=20))
    assert found, "no jobs came back"
    for posting in found:
        assert posting.url.startswith("https://") and posting.title and posting.arrangement == "remote"
        assert posting.worldwide or posting.countries or posting.location == "Remote"
    first = found[0]
    assert source.check([(first.source_id, first.url)]) == {first.source_id: "open"}
    print(f"\nHimalayas: {len(found)} jobs, e.g. {first.title} - {first.location}")


def test_jobicy():
    source = JobicySource(Feed(Fetcher(min_interval=2.0)))
    feed = source.feed.current()
    postings = [to_posting(raw) for raw in feed]
    assert feed and all(postings), "a job in the feed couldn't be read"
    unknown = [p.location for p in postings if not p.countries and not p.worldwide]
    statuses = source.check([(p.source_id, p.url) for p in postings[:3]])
    assert set(statuses.values()) <= {"open", "closed", "unknown"} and len(statuses) == 3
    print(f"\nJobicy: {len(feed)} jobs in the feed; places not recognised: {sorted(set(unknown)) or 'none'}")
