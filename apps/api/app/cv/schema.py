"""A CV as structured data. Every field is plain text - the PDF builder
escapes it, so nothing typed here can act as LaTeX."""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.presets import LANGUAGE_LEVELS


def _clean(text: str) -> str:
    """Strips the ends and drops control characters (newlines too: every
    field is one line; lists hold several)."""
    text = "".join(" " if ch.isspace() else ch for ch in text if ch.isspace() or unicodedata.category(ch)[0] != "C")
    return re.sub(r" {2,}", " ", text).strip()


Line = Annotated[str, AfterValidator(_clean)]
_URL = re.compile(r"^https?://[^\s<>\"{}|\\^`]+$")


def _url(value: str) -> str:
    value = _clean(value)
    if value and not _URL.match(value):
        raise ValueError("a link must start with http:// or https:// and have no spaces")
    return value


class Experience(BaseModel):
    title: Annotated[Line, Field(max_length=120)]
    employer: Annotated[Line, Field(max_length=120)] = ""
    location: Annotated[Line, Field(max_length=80)] = ""
    start: Annotated[Line, Field(max_length=30)] = ""  # as they write it: "Jan 2024", "2019"
    end: Annotated[Line, Field(max_length=30)] = ""  # "" = to date
    bullets: Annotated[list[Annotated[Line, Field(max_length=300)]], Field(max_length=8)] = []


class Education(BaseModel):
    qualification: Annotated[Line, Field(max_length=160)]
    institution: Annotated[Line, Field(max_length=120)] = ""
    location: Annotated[Line, Field(max_length=80)] = ""
    start: Annotated[Line, Field(max_length=30)] = ""
    end: Annotated[Line, Field(max_length=30)] = ""
    details: Annotated[Line, Field(max_length=300)] = ""


class CvLanguage(BaseModel):
    name: Annotated[Line, Field(min_length=1, max_length=60)]
    level: str = "professional"

    @field_validator("level")
    @classmethod
    def _level(cls, value: str) -> str:
        if value not in dict(LANGUAGE_LEVELS):
            raise ValueError(f"level must be one of {', '.join(dict(LANGUAGE_LEVELS))}")
        return value


class CvContent(BaseModel):
    name: Annotated[Line, Field(max_length=120)] = ""
    headline: Annotated[Line, Field(max_length=160)] = ""
    email: Annotated[Line, Field(max_length=200)] = ""
    phone: Annotated[Line, Field(max_length=40)] = ""
    location: Annotated[Line, Field(max_length=80)] = ""
    links: Annotated[list[Annotated[str, AfterValidator(_url), Field(max_length=200)]], Field(max_length=4)] = []
    summary: Annotated[Line, Field(max_length=1200)] = ""
    experience: Annotated[list[Experience], Field(max_length=15)] = []
    education: Annotated[list[Education], Field(max_length=8)] = []
    skills: Annotated[list[Annotated[Line, Field(max_length=60)]], Field(max_length=40)] = []
    languages: Annotated[list[CvLanguage], Field(max_length=10)] = []

    @field_validator("links", "skills")
    @classmethod
    def _no_blanks(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(v for v in values if v))

    @field_validator("experience")
    @classmethod
    def _experience(cls, values: list[Experience]) -> list[Experience]:
        return [v.model_copy(update={"bullets": [b for b in v.bullets if b]}) for v in values if v.title]

    @field_validator("education")
    @classmethod
    def _education(cls, values: list[Education]) -> list[Education]:
        return [v for v in values if v.qualification]

    def is_empty(self) -> bool:
        return not (self.name or self.experience or self.education or self.summary)
