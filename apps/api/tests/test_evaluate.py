"""Deal-breaker checks and verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.matching.evaluate import evaluate
from app.presets import get_catalog


@dataclass
class Job:
    title: str = "Staff Nurse"
    location: str = "Manchester"
    country: str = "GB"
    arrangement: str = "onsite"
    salary_min: int | None = 33000
    salary_max: int | None = 38000
    salary_currency: str = "GBP"
    salary_period: str = "year"
    countries: tuple = ()
    worldwide: bool = False


@dataclass
class Profile:
    seniority_levels: list = field(default_factory=lambda: ["mid", "senior"])
    locations: list = field(default_factory=lambda: ["Manchester"])
    work_arrangements: list = field(default_factory=lambda: ["onsite", "hybrid"])
    authorized_countries: list = field(default_factory=lambda: ["GB"])
    open_to_sponsorship: bool = False
    salary_min: int | None = 32000
    salary_currency: str = "GBP"
    salary_period: str = "year"


def run(job=None, profile=None):
    catalog = get_catalog()
    roles = catalog.industries["healthcare"].roles
    result = evaluate(job or Job(), profile or Profile(), roles, catalog.levels_for("healthcare"),
                      {lv.key: lv.label for lv in catalog.levels}, catalog.countries)
    return result.verdict, {c.key: (c.status, c.detail) for c in result.checks}


def test_a_job_that_fits():
    verdict, checks = run()
    assert verdict == "match"
    assert checks["role"] == ("pass", "Registered nurse (matched “staff nurse”)")
    assert checks["salary"] == ("pass", "£33,000-£38,000 a year")
    assert checks["permit"] == ("pass", "United Kingdom - no visa needed")


@pytest.mark.parametrize("job,key,status,detail", [
    (Job(title="Primary Teacher"), "role", "fail", "Not one of your target roles"),
    (Job(title="Lead Staff Nurse"), "level", "fail", "Lead or principal - you’re after mid level or senior"),
    (Job(arrangement="remote", location="Remote (UK)"), "arrangement", "fail", "Remote - you’re after on-site or hybrid"),
    (Job(location="Leeds"), "location", "fail", "Leeds - not one of your locations"),
    (Job(country="CA", location="Toronto, ON"), "permit", "fail", "Canada - you’d need a visa"),
])
def test_each_deal_breaker_filters(job, key, status, detail):
    verdict, checks = run(job)
    assert verdict == "filtered" and checks[key] == (status, detail)


def test_flags_are_worth_a_look_not_a_veto():
    verdict, checks = run(Job(salary_min=26000, salary_max=30000))
    assert verdict == "flagged" and checks["salary"] == ("flag", "£26,000-£30,000 a year - below your £32,000")
    verdict, checks = run(Job(country="IE", location="Manchester"), Profile(open_to_sponsorship=True))
    assert verdict == "flagged" and checks["permit"][0] == "flag"


def test_what_the_posting_doesnt_say_is_unknown_not_a_failure():
    verdict, checks = run(Job(arrangement="", country="", salary_min=None, salary_max=None, location=""))
    assert verdict == "match"
    assert {checks[k][0] for k in ("arrangement", "location", "permit", "salary")} == {"unknown"}
    _, checks = run(Job(salary_currency="EUR"))
    assert checks["salary"] == ("unknown", "€33,000-€38,000 a year - not in your currency and period, so not compared")


def test_an_open_profile_lets_everything_through():
    open_profile = Profile(seniority_levels=[], locations=[], work_arrangements=[], authorized_countries=[], salary_min=None)
    verdict, checks = run(Job(title="Lead Staff Nurse", location="Leeds", arrangement="remote"), open_profile)
    assert verdict == "match" and "salary" not in checks
    assert checks["permit"][0] == "unknown"


def test_remote_only_profiles():
    remote_only = Profile(locations=["Remote (UK)"], work_arrangements=[])
    assert run(Job(arrangement="remote", location="Remote (UK)"), remote_only)[0] == "match"
    verdict, checks = run(Job(location="Leeds"), remote_only)
    assert verdict == "filtered" and checks["location"] == ("fail", "Leeds - you’re looking for remote work")
