"""What each preset file may contain. Unknown keys are errors, so a typo in a
preset fails the tests instead of being ignored."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

KEY = r"^[a-z0-9]+(-[a-z0-9]+)*$"
Key = Annotated[str, StringConstraints(pattern=KEY, max_length=64)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Phrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RoleFile(_File):
    key: Key
    label: Label
    titles: list[Phrase] = Field(min_length=1)
    exclude: list[Phrase] = []
    search: list[Phrase] = Field(min_length=1)


class IndustryFile(_File):
    label: Label
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    skills: list[Phrase] = []
    scoring: dict[str, int]
    seniority: dict[str, list[Phrase]] = {}
    roles: list[RoleFile] = Field(min_length=1)


class MarketFile(_File):
    label: Label
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    salary_period: str = "year"
    locations: list[Label] = []
    arrangements: list[str] = []
    countries: dict[Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")], Label] = {}


class LevelFile(_File):
    key: Key
    label: Label
    words: list[Phrase] = []


class SeniorityFile(_File):
    levels: list[LevelFile] = Field(min_length=2)


class DimensionFile(_File):
    label: Label
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class BandFile(_File):
    min: int = Field(ge=0, le=100)
    label: Label
    advice: Label


class ScoringFile(_File):
    dimensions: dict[Key, DimensionFile] = Field(min_length=1)
    bands: list[BandFile] = Field(min_length=1)
