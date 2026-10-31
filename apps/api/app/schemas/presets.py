"""The presets as the API serves them (app/presets, presets/ at the repo root)."""

from __future__ import annotations

from pydantic import BaseModel


class Option(BaseModel):
    key: str
    label: str


class IndustrySummary(Option):
    description: str


class MarketSummary(Option):
    currency: str


class PresetsRead(BaseModel):
    """Everything the profile forms choose from."""

    industries: list[IndustrySummary]
    markets: list[MarketSummary]
    levels: list[Option]
    arrangements: list[Option]
    salary_periods: list[Option]
    language_levels: list[Option]
    countries: list[Option]  # key: ISO 3166-1 alpha-2 code
    currencies: list[str]
    application_statuses: list[Option]


class RoleRead(Option):
    titles: list[str]
    exclude: list[str]
    search: list[str]


class DimensionRead(Option):
    description: str
    weight: int  # percent


class IndustryRead(IndustrySummary):
    skills: list[str]
    roles: list[RoleRead]
    scoring: list[DimensionRead]
    seniority: dict[str, list[str]]  # level key -> this industry's extra title words


class MarketRead(MarketSummary):
    salary_period: str
    locations: list[str]
    arrangements: list[str]
    countries: list[Option]
