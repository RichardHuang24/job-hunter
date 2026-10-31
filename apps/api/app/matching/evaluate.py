"""A job against a person's profile: which of their roles it is, and whether
it passes their deal-breakers. Pure.

Each check says pass, flag (worth a look, but check the posting), fail (a
deal-breaker) or unknown (the posting doesn't say). The verdict:

- "filtered": any check failed - left out of the main list
- "flagged": nothing failed, but something needs a look
- "match": everything known passes
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.matching.titles import LevelLike, TargetLike, match_title, normalize, spans

PASS, FLAG, FAIL, UNKNOWN = "pass", "flag", "fail", "unknown"
ARRANGEMENT_LABELS = {"onsite": "On-site", "hybrid": "Hybrid", "remote": "Remote"}
SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$", "CAD": "CA$", "AUD": "A$"}
PERIOD_WORDS = {"year": "a year", "month": "a month", "day": "a day", "hour": "an hour"}


class JobLike(Protocol):
    title: str
    location: str
    country: str
    arrangement: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    salary_period: str


class ProfileLike(Protocol):
    seniority_levels: list[str]
    locations: list[str]
    work_arrangements: list[str]
    authorized_countries: list[str]
    open_to_sponsorship: bool
    salary_min: int | None
    salary_currency: str
    salary_period: str


@dataclass(frozen=True)
class Check:
    key: str  # role, level, arrangement, location, permit, salary
    status: str  # pass, flag, fail, unknown
    detail: str


@dataclass(frozen=True)
class Evaluation:
    target: TargetLike | None
    phrase: str
    level: str
    verdict: str  # match, flagged, filtered
    checks: tuple[Check, ...]


def money(amount: int, currency: str) -> str:
    symbol = SYMBOLS.get(currency)
    return f"{symbol}{amount:,}" if symbol else f"{amount:,} {currency}"


def _or_list(labels: list[str]) -> str:
    labels = [label.lower() for label in labels]
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]


def is_remote_place(place: str) -> bool:
    return normalize(place).startswith("remote")


def _role(found: TargetLike | None, phrase: str) -> Check:
    if found is None:
        return Check("role", FAIL, "Not one of your target roles")
    return Check("role", PASS, f"{found.label} (matched “{phrase}”)")


def _level(level: str, wanted: Sequence[str], labels: Mapping[str, str]) -> Check:
    label = labels.get(level, level)
    if not wanted:
        return Check("level", PASS, label)
    if level in wanted:
        return Check("level", PASS, label)
    return Check("level", FAIL, f"{label} - you’re after {_or_list([labels.get(k, k) for k in wanted])}")


def _arrangement(job: JobLike, profile: ProfileLike) -> Check:
    if not job.arrangement:
        return Check("arrangement", UNKNOWN, "The posting doesn’t say on-site, hybrid or remote")
    label = ARRANGEMENT_LABELS.get(job.arrangement, job.arrangement)
    if not profile.work_arrangements or job.arrangement in profile.work_arrangements:
        return Check("arrangement", PASS, label)
    wanted = [ARRANGEMENT_LABELS.get(a, a) for a in profile.work_arrangements]
    return Check("arrangement", FAIL, f"{label} - you’re after {_or_list(wanted)}")


def _location(job: JobLike, profile: ProfileLike) -> Check:
    places = [p for p in profile.locations if not is_remote_place(p)]
    if job.arrangement == "remote":
        return Check("location", PASS, job.location or "Remote")
    if not job.location:
        return Check("location", UNKNOWN, "The posting doesn’t say where")
    if not profile.locations:
        return Check("location", PASS, job.location)
    text = normalize(job.location)
    if any(spans(normalize(place), text) for place in places):
        return Check("location", PASS, job.location)
    if not places:
        return Check("location", FAIL, f"{job.location} - you’re looking for remote work")
    return Check("location", FAIL, f"{job.location} - not one of your locations")


def _permit(job: JobLike, profile: ProfileLike, countries: Mapping[str, str]) -> Check:
    if not job.country:
        return Check("permit", UNKNOWN, "The posting doesn’t say which country")
    name = countries.get(job.country, job.country)
    if not profile.authorized_countries:
        return Check("permit", UNKNOWN, f"{name} - add where you can work to check this")
    if job.country in profile.authorized_countries:
        return Check("permit", PASS, f"{name} - no visa needed")
    if profile.open_to_sponsorship:
        return Check("permit", FLAG, f"{name} - you’d need a visa; check the job offers sponsorship")
    return Check("permit", FAIL, f"{name} - you’d need a visa")


def _salary(job: JobLike, profile: ProfileLike) -> Check | None:
    if profile.salary_min is None:
        return None
    top = job.salary_max if job.salary_max is not None else job.salary_min
    if top is None or not job.salary_currency:
        return Check("salary", UNKNOWN, "The posting doesn’t give a salary")
    low = job.salary_min if job.salary_min is not None else top
    stated = money(low, job.salary_currency) + (f"-{money(top, job.salary_currency)}" if top != low else "")
    stated += f" {PERIOD_WORDS.get(job.salary_period, job.salary_period)}".rstrip()
    if job.salary_currency != profile.salary_currency or (job.salary_period or "year") != profile.salary_period:
        return Check("salary", UNKNOWN, f"{stated} - not in your currency and period, so not compared")
    if top < profile.salary_min:
        return Check("salary", FLAG, f"{stated} - below your {money(profile.salary_min, profile.salary_currency)}")
    return Check("salary", PASS, stated)


def evaluate(
    job: JobLike,
    profile: ProfileLike,
    targets: Sequence[TargetLike],
    levels: Sequence[LevelLike],
    level_labels: Mapping[str, str],
    countries: Mapping[str, str],
) -> Evaluation:
    found = match_title(job.title, targets, levels)
    checks = [
        _role(found.target, found.phrase),
        _level(found.level, profile.seniority_levels, level_labels),
        _arrangement(job, profile),
        _location(job, profile),
        _permit(job, profile, countries),
    ]
    salary = _salary(job, profile)
    if salary is not None:
        checks.append(salary)
    statuses = {check.status for check in checks}
    verdict = "filtered" if FAIL in statuses else "flagged" if FLAG in statuses else "match"
    return Evaluation(found.target, found.phrase, found.level, verdict, tuple(checks))
