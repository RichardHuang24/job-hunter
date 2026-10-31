"""Sample jobs, built in: Job Hunter shows something on its first run with no
API keys, and the tests and smoke test have predictable data. Every company
is fictional, and the app labels these as samples."""

from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

from app.matching.titles import normalize, spans
from app.sources.base import Posting, Query, Source

DATA = Path(__file__).with_name("demo_jobs.json")


@lru_cache
def _jobs() -> tuple[dict, ...]:
    return tuple(json.loads(DATA.read_text(encoding="utf-8")))


def _has_words(text: str, phrase: str) -> bool:
    text = normalize(text)
    return all(spans(word, text) for word in normalize(phrase).split())


class DemoSource(Source):
    key = "demo"
    label = "Sample jobs"
    description = "Built-in sample postings with fictional employers, so you can try Job Hunter without any job board."
    commercial = True  # our own data
    demo = True

    def search(self, query: Query) -> list[Posting]:
        today = dt.datetime.now(dt.UTC).replace(hour=9, minute=0, second=0, microsecond=0)
        out = []
        for job in _jobs():
            if not _has_words(job["title"], query.term):
                continue
            remote = job["arrangement"] == "remote"
            if query.countries and job["country"] not in query.countries:
                continue
            if query.remote and not remote:
                continue
            if query.location and not query.remote and not _has_words(job["location"], query.location):
                continue
            salary = job.get("salary") or [None, None, "", ""]
            out.append(Posting(
                source_id=job["id"], url=f"https://example.com/jobs/{job['id']}", title=job["title"],
                company=job["company"], location=job["location"], country=job["country"],
                arrangement=job["arrangement"], salary_min=salary[0], salary_max=salary[1],
                salary_currency=salary[2], salary_period=salary[3],
                posted_at=today - dt.timedelta(days=job["days_ago"]), description=job["description"],
            ))
            if len(out) >= query.limit:
                break
        return out
