"""Job sources, saved searches and their runs."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.presets import get_catalog
from app.schemas.me import Text, UtcDatetime, clean_list
from app.sources import SOURCES


class SourceRead(BaseModel):
    key: str
    label: str
    description: str
    homepage: str
    countries: list[str]  # [] = anywhere
    commercial: bool
    demo: bool


class SearchFields(BaseModel):
    name: Annotated[Text, Field(min_length=1, max_length=80)]
    terms: list[str]
    locations: list[str] = []
    countries: list[str] = []
    include_remote: bool = False
    sources: list[str] = []
    daily: bool = True


class SearchWrite(SearchFields):
    model_config = ConfigDict(extra="forbid")

    @field_validator("terms")
    @classmethod
    def _terms(cls, values: list[str]) -> list[str]:
        values = clean_list(values, max_length=100)
        if not values:
            raise ValueError("needs at least one thing to search for")
        if len(values) > 10:
            raise ValueError("10 search terms at most")
        return values

    @field_validator("locations")
    @classmethod
    def _locations(cls, values: list[str]) -> list[str]:
        values = clean_list(values, max_length=100)
        if len(values) > 10:
            raise ValueError("10 locations at most")
        return values

    @field_validator("countries")
    @classmethod
    def _countries(cls, values: list[str]) -> list[str]:
        known = get_catalog().countries
        values = list(dict.fromkeys(v.strip().upper() for v in values))
        unknown = [v for v in values if v not in known]
        if unknown:
            raise ValueError(f"{unknown[0]!r} isn't a known country code - see GET /presets")
        if len(values) > 5:
            raise ValueError("5 countries at most")
        return values

    @field_validator("sources")
    @classmethod
    def _sources(cls, values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in SOURCES]
        if unknown:
            raise ValueError(f"{unknown[0]!r} isn't a job source - see GET /sources")
        return list(dict.fromkeys(values))


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    search_id: str
    status: str  # queued, running, succeeded, failed
    trigger: str  # manual, schedule, onboarding
    counts: dict  # queries, found, new, matches, flagged, filtered, by_source
    errors: list[dict]  # [{"source": "...", "message": "..."}]
    created_at: UtcDatetime
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None


class SearchRead(SearchFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    next_run_at: UtcDatetime | None
    last_run_at: UtcDatetime | None
    created_at: UtcDatetime
    last_run: RunRead | None = None  # the newest run, finished or not
