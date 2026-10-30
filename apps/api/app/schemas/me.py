from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.presets import INDUSTRY_KEYS, MARKET_KEYS


def _utc(value: dt.datetime) -> dt.datetime:
    """SQLite hands back naive datetimes; every one we store is UTC."""
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


UtcDatetime = Annotated[dt.datetime, AfterValidator(_utc)]
Text = Annotated[str, AfterValidator(str.strip)]


def _one_of(keys: frozenset[str], what: str):
    def check(value: str) -> str:
        if value and value not in keys:
            raise ValueError(f"isn't a known {what} - see GET /presets")
        return value

    return AfterValidator(check)


class ProfileWrite(BaseModel):
    display_name: Annotated[Text, Field(max_length=255)] = ""
    headline: Annotated[Text, Field(max_length=255)] = ""
    industry: Annotated[Text, Field(max_length=64), _one_of(INDUSTRY_KEYS, "industry")] = ""
    market: Annotated[Text, Field(max_length=64), _one_of(MARKET_KEYS, "market")] = ""


class ProfileRead(ProfileWrite):
    model_config = ConfigDict(from_attributes=True)

    updated_at: UtcDatetime


class MeRead(BaseModel):
    id: int
    email: str | None
    name: str | None
    profile: ProfileRead | None


class Preset(BaseModel):
    key: str
    label: str


class PresetsRead(BaseModel):
    industries: list[Preset]
    markets: list[Preset]
