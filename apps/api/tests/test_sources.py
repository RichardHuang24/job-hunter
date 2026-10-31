"""The job source registry and the built-in sample jobs."""

from __future__ import annotations

from app.config import Settings
from app.sources import SOURCES, enabled_sources
from app.sources.base import Posting, Query, Source
from app.sources.demo import DemoSource, _jobs


def test_sample_jobs_are_well_formed():
    jobs = _jobs()
    assert len(jobs) >= 50
    assert len({j["id"] for j in jobs}) == len(jobs)
    for job in jobs:
        assert job["arrangement"] in ("onsite", "hybrid", "remote")
        assert job["country"] == "" or len(job["country"]) == 2
        assert "fictional" in job["description"]


def test_the_demo_source_filters_like_a_job_board():
    demo = DemoSource()
    titles = lambda q: {p.title for p in demo.search(q)}  # noqa: E731
    in_manchester = titles(Query("staff nurse", location="Manchester", countries=("GB",)))
    assert {"Staff Nurse - Acute Medicine", "Senior Staff Nurse - Band 6", "Lead Staff Nurse - Band 7"} <= in_manchester
    assert all("Nurse" in t for t in in_manchester)
    assert titles(Query("registered nurse", location="Manchester", countries=("GB",))) >= {
        "Registered Nurse - Day Surgery", "Registered Nurse - Nights"}  # "Greater Manchester" counts
    assert "Registered Nurse - Community" not in titles(Query("registered nurse", countries=("GB",)))
    assert titles(Query("registered nurse", remote=True, countries=("GB",))) == {"Registered Nurse - Telephone Triage"}
    assert not titles(Query("nurse", countries=("GB",))) & {"Lecturer in Nursing"}  # whole words only
    posting = demo.search(Query("pharmacist"))[0]
    assert posting.url.startswith("https://example.com/") and posting.salary_currency == "EUR"
    assert len(demo.search(Query("nurse", limit=2))) == 2


class _Keyed(Source):
    key, label, description, commercial, needs_key = "keyed", "Keyed", "Needs a key", False, "backend_jwt_secret"

    def search(self, query: Query) -> list[Posting]:
        return []


def test_which_sources_are_enabled(monkeypatch):
    monkeypatch.setitem(SOURCES, "keyed", _Keyed)
    keys = lambda **kw: [s.key for s in enabled_sources(Settings(**kw))]  # noqa: E731
    assert keys() == ["demo"]
    assert keys(job_sources="demo, keyed, nowhere", backend_jwt_secret="") == ["demo"]  # no key yet
    assert keys(job_sources="demo,keyed", backend_jwt_secret="x" * 40) == ["demo", "keyed"]
    assert keys(job_sources="demo,keyed", backend_jwt_secret="x" * 40, commercial_only=True) == ["demo"]
    assert keys(job_sources="") == []


def test_a_source_covers_its_countries():
    class UkOnly(_Keyed):
        countries = ("GB",)
    assert UkOnly().covers(Query("x", countries=("GB", "IE")))
    assert not UkOnly().covers(Query("x", countries=("US",)))
    assert UkOnly().covers(Query("x"))
