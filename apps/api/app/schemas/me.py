"""The signed-in user: profile, target roles, onboarding, title checks.

Writes are checked against the presets (app/presets): an industry, market,
level, country or currency must be one the catalog knows. Reads aren't, so a
preset removed later never stops anyone loading their profile.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.matching.titles import normalize
from app.presets import ARRANGEMENTS, LANGUAGE_LEVELS, SALARY_PERIODS, get_catalog


def _utc(value: dt.datetime) -> dt.datetime:
    """SQLite hands back naive datetimes; every one we store is UTC."""
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


UtcDatetime = Annotated[dt.datetime, AfterValidator(_utc)]
Text = Annotated[str, AfterValidator(str.strip)]

MAX_TARGETS = 12


def clean_list(values: list[str], *, max_length: int) -> list[str]:
    """Trimmed, without blanks or repeats (ignoring case), in the order given."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = " ".join(str(value).split())
        if not value:
            continue
        if len(value) > max_length:
            raise ValueError(f"'{value[:20]}...' is longer than {max_length} characters")
        if value.casefold() not in seen:
            seen.add(value.casefold())
            out.append(value)
    return out


def clean_phrases(values: list[str]) -> list[str]:
    """Title phrases, normalised the way matching reads them ('Front-End' -> 'front end')."""
    return list(dict.fromkeys(p for p in (normalize(v) for v in clean_list(values, max_length=80)) if p))


def _in_order(values: list[str], allowed: tuple[str, ...], what: str) -> list[str]:
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise ValueError(f"{unknown[0]!r} isn't a known {what} - see GET /presets")
    return [key for key in allowed if key in values]


# --- Profile ------------------------------------------------------------------------------


class Language(BaseModel):
    name: Annotated[Text, Field(min_length=1, max_length=60)]
    level: str = "professional"


class ProfileFields(BaseModel):
    display_name: Annotated[Text, Field(max_length=255)] = ""
    headline: Annotated[Text, Field(max_length=255)] = ""
    summary: Annotated[Text, Field(max_length=4000)] = ""
    industry: Annotated[Text, Field(max_length=64)] = ""
    market: Annotated[Text, Field(max_length=64)] = ""
    years_experience: Annotated[int | None, Field(ge=0, le=60)] = None
    seniority_levels: Annotated[list[str], Field(max_length=10)] = []
    skills: Annotated[list[str], Field(max_length=50)] = []
    languages: Annotated[list[Language], Field(max_length=10)] = []
    locations: Annotated[list[str], Field(max_length=20)] = []
    work_arrangements: Annotated[list[str], Field(max_length=3)] = []
    authorized_countries: Annotated[list[str], Field(max_length=60)] = []
    open_to_sponsorship: bool = False
    salary_min: Annotated[int | None, Field(ge=0, le=10_000_000)] = None
    salary_currency: Annotated[Text, Field(max_length=3)] = ""
    salary_period: Annotated[Text, Field(max_length=8)] = "year"


class ProfileWrite(ProfileFields):
    model_config = ConfigDict(extra="forbid")

    @field_validator("industry")
    @classmethod
    def _industry(cls, value: str) -> str:
        if value and value not in get_catalog().industries:
            raise ValueError("isn't a known industry - see GET /presets")
        return value

    @field_validator("market")
    @classmethod
    def _market(cls, value: str) -> str:
        if value and value not in get_catalog().markets:
            raise ValueError("isn't a known market - see GET /presets")
        return value

    @field_validator("seniority_levels")
    @classmethod
    def _levels(cls, values: list[str]) -> list[str]:
        return _in_order(values, get_catalog().level_keys, "seniority level")

    @field_validator("work_arrangements")
    @classmethod
    def _arrangements(cls, values: list[str]) -> list[str]:
        return _in_order(values, tuple(key for key, _ in ARRANGEMENTS), "work arrangement")

    @field_validator("authorized_countries")
    @classmethod
    def _countries(cls, values: list[str]) -> list[str]:
        known = get_catalog().countries
        values = [v.strip().upper() for v in values]
        unknown = [v for v in values if v not in known]
        if unknown:
            raise ValueError(f"{unknown[0]!r} isn't a known country code - see GET /presets")
        return list(dict.fromkeys(values))

    @field_validator("skills")
    @classmethod
    def _skills(cls, values: list[str]) -> list[str]:
        return clean_list(values, max_length=80)

    @field_validator("locations")
    @classmethod
    def _locations(cls, values: list[str]) -> list[str]:
        return clean_list(values, max_length=100)

    @field_validator("languages")
    @classmethod
    def _languages(cls, values: list[Language]) -> list[Language]:
        levels = {key for key, _ in LANGUAGE_LEVELS}
        out, seen = [], set()
        for language in values:
            if language.level not in levels:
                raise ValueError(f"{language.level!r} isn't a language level - see GET /presets")
            if language.name.casefold() not in seen:
                seen.add(language.name.casefold())
                out.append(language)
        return out

    @field_validator("salary_currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        value = value.upper()
        if value and value not in get_catalog().currencies:
            raise ValueError("isn't a supported currency - see GET /presets")
        return value

    @field_validator("salary_period")
    @classmethod
    def _period(cls, value: str) -> str:
        if value not in {key for key, _ in SALARY_PERIODS}:
            raise ValueError("isn't a salary period - see GET /presets")
        return value

    @model_validator(mode="after")
    def _salary_needs_a_currency(self) -> ProfileWrite:
        if self.salary_min is not None and not self.salary_currency:
            raise ValueError("salary_currency: say which currency the minimum salary is in")
        return self


class ProfileRead(ProfileFields):
    model_config = ConfigDict(from_attributes=True)

    onboarded_at: UtcDatetime | None
    updated_at: UtcDatetime


# --- Target roles -------------------------------------------------------------------------


class TargetFields(BaseModel):
    label: Annotated[Text, Field(min_length=1, max_length=80)]
    titles: list[str]
    exclude: list[str] = []
    search: list[str] = []
    preset_role: Annotated[Text, Field(max_length=130)] = ""


class TargetWrite(TargetFields):
    model_config = ConfigDict(extra="forbid")

    @field_validator("titles")
    @classmethod
    def _titles(cls, values: list[str]) -> list[str]:
        values = clean_phrases(values)
        if not values:
            raise ValueError("needs at least one job title")
        if len(values) > 20:
            raise ValueError("20 job titles at most")
        return values

    @field_validator("exclude")
    @classmethod
    def _exclude(cls, values: list[str]) -> list[str]:
        values = clean_phrases(values)
        if len(values) > 20:
            raise ValueError("20 excluded titles at most")
        return values

    @field_validator("search")
    @classmethod
    def _search(cls, values: list[str]) -> list[str]:
        values = clean_list(values, max_length=100)
        if len(values) > 10:
            raise ValueError("10 search terms at most")
        return values

    @field_validator("preset_role")
    @classmethod
    def _preset_role(cls, value: str) -> str:
        if value:
            industry, _, role = value.partition("/")
            found = get_catalog().industries.get(industry)
            if found is None or found.role(role) is None:
                raise ValueError("isn't a preset role ('industry/role') - see GET /presets/industries/{key}")
        return value

    @model_validator(mode="after")
    def _search_defaults_to_the_label(self) -> TargetWrite:
        if not self.search:
            self.search = [self.label]
        return self


class TargetRead(TargetFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int


def check_target_count(targets: list) -> list:
    if len(targets) > MAX_TARGETS:
        raise ValueError(f"{MAX_TARGETS} target roles at most")
    return targets


TargetList = Annotated[list[TargetWrite], AfterValidator(check_target_count)]


# --- Onboarding ---------------------------------------------------------------------------


class OnboardingWrite(ProfileWrite):
    """The whole first-run setup in one call: the profile, plus the roles to
    go after - preset roles of the chosen industry, by key, and any others."""

    roles: list[str] = []
    custom_roles: list[TargetWrite] = []

    @model_validator(mode="after")
    def _complete(self) -> OnboardingWrite:
        if not self.industry or not self.market:
            raise ValueError("choose an industry and a market")
        industry = get_catalog().industries[self.industry]
        unknown = [key for key in self.roles if industry.role(key) is None]
        if unknown:
            raise ValueError(f"roles: {unknown[0]!r} isn't a role in {industry.label}")
        count = len(set(self.roles)) + len(self.custom_roles)
        if count == 0:
            raise ValueError("choose at least one role")
        if count > MAX_TARGETS:
            raise ValueError(f"{MAX_TARGETS} target roles at most")
        return self


class MeRead(BaseModel):
    id: int
    email: str | None
    name: str | None
    is_admin: bool = False  # in ADMIN_EMAILS: can open /admin
    profile: ProfileRead | None
    targets: list[TargetRead]


# --- Title check --------------------------------------------------------------------------


class TitleCheckWrite(BaseModel):
    title: Annotated[Text, Field(min_length=1, max_length=200)]


class Named(BaseModel):
    key: str
    label: str


class TitleCheckRead(BaseModel):
    title: str
    target: TargetRead | None  # the role it counts as, if any
    matched: str  # the phrase that matched it
    level: Named
    level_words: list[str]  # the words that set the level; [] means none (mid level)
    wanted: bool  # one of their roles, at a level they're after
    explanation: str
