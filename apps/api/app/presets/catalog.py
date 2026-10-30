"""Loads the presets and checks them against each other.

The files say what each industry and market is; this module turns them into
one `Catalog`, normalising title phrases (lowercase, punctuation to spaces)
so matching code never has to. Anything inconsistent - a duplicate role, a
seniority level that doesn't exist, scoring weights that don't add up to 100
- raises PresetError naming the file, at startup and in the tests.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.config import get_settings
from app.matching.titles import normalize
from app.presets.files import KEY, IndustryFile, MarketFile, ScoringFile, SeniorityFile

# Profile choices that are the same for every industry and market.
ARRANGEMENTS: tuple[tuple[str, str], ...] = (("onsite", "On-site"), ("hybrid", "Hybrid"), ("remote", "Remote"))
SALARY_PERIODS: tuple[tuple[str, str], ...] = (
    ("year", "per year"), ("month", "per month"), ("day", "per day"), ("hour", "per hour"),
)
LANGUAGE_LEVELS: tuple[tuple[str, str], ...] = (
    ("basic", "Basic"), ("conversational", "Conversational"), ("professional", "Professional"),
    ("native", "Native or bilingual"),
)


class PresetError(ValueError):
    """A preset file is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class Level:
    key: str
    label: str
    words: tuple[str, ...]


@dataclass(frozen=True)
class Role:
    key: str
    label: str
    titles: tuple[str, ...]
    exclude: tuple[str, ...]
    search: tuple[str, ...]


@dataclass(frozen=True)
class Industry:
    key: str
    label: str
    description: str
    skills: tuple[str, ...]
    scoring: dict[str, int]
    seniority: dict[str, tuple[str, ...]]  # level key -> extra title words
    roles: tuple[Role, ...]

    def role(self, key: str) -> Role | None:
        return next((r for r in self.roles if r.key == key), None)


@dataclass(frozen=True)
class Market:
    key: str
    label: str
    currency: str
    salary_period: str
    locations: tuple[str, ...]
    arrangements: tuple[str, ...]
    countries: dict[str, str]


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class Band:
    min: int
    label: str
    advice: str


@dataclass(frozen=True)
class Catalog:
    industries: dict[str, Industry]  # ordered by label
    markets: dict[str, Market]  # ordered by label
    levels: tuple[Level, ...]  # lowest first
    dimensions: dict[str, Dimension]
    bands: tuple[Band, ...]  # highest first
    countries: dict[str, str] = field(default_factory=dict)  # every market's, ordered by name
    currencies: tuple[str, ...] = ()

    @property
    def level_keys(self) -> tuple[str, ...]:
        return tuple(level.key for level in self.levels)

    def levels_for(self, industry: str) -> tuple[Level, ...]:
        """The seniority levels with this industry's extra words added."""
        extra = self.industries[industry].seniority if industry in self.industries else {}
        return tuple(Level(lv.key, lv.label, lv.words + extra.get(lv.key, ())) for lv in self.levels)


def _read(path: Path, model):
    try:
        return model.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except tomllib.TOMLDecodeError as exc:
        raise PresetError(f"{path.name}: not valid TOML - {exc}") from exc
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise PresetError(f"{path.name}: {where}: {first['msg']}") from exc


def _phrases(path: Path, what: str, phrases: list[str]) -> tuple[str, ...]:
    out = []
    for phrase in phrases:
        normal = normalize(phrase)
        if not normal:
            raise PresetError(f"{path.name}: {what}: {phrase!r} has no letters or digits")
        if normal in out:
            raise PresetError(f"{path.name}: {what}: {phrase!r} is listed twice")
        out.append(normal)
    return tuple(out)


def _unique(path: Path, what: str, values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    for value in values:
        if value.casefold() in seen:
            raise PresetError(f"{path.name}: {what}: {value!r} is listed twice")
        seen.add(value.casefold())
    return tuple(values)


def _stem(path: Path) -> str:
    if not re.match(KEY, path.stem):
        raise PresetError(f"{path.name}: file names are lowercase words joined by hyphens")
    return path.stem


def load_catalog(root: Path) -> Catalog:
    if not (root / "industries").is_dir() or not (root / "markets").is_dir():
        raise PresetError(f"{root} has no industries/ and markets/ folders")
    seniority = _read(root / "seniority.toml", SeniorityFile)
    scoring = _read(root / "scoring.toml", ScoringFile)

    levels = []
    for lv in seniority.levels:
        if any(lv.key == other.key for other in levels):
            raise PresetError(f"seniority.toml: level {lv.key!r} is listed twice")
        levels.append(Level(lv.key, lv.label, _phrases(root / "seniority.toml", lv.key, lv.words)))
    level_keys = {lv.key for lv in levels}

    mins = [band.min for band in scoring.bands]
    if mins != sorted(mins, reverse=True) or len(set(mins)) != len(mins) or mins[-1] != 0:
        raise PresetError("scoring.toml: bands go from the highest min down to a band with min = 0")
    dimensions = {key: Dimension(key, d.label, d.description) for key, d in scoring.dimensions.items()}

    industries = []
    for path in sorted((root / "industries").glob("*.toml")):
        data = _read(path, IndustryFile)
        if set(data.scoring) != set(dimensions):
            raise PresetError(f"{path.name}: scoring needs exactly these dimensions: {', '.join(dimensions)}")
        if any(w < 0 for w in data.scoring.values()) or sum(data.scoring.values()) != 100:
            raise PresetError(f"{path.name}: scoring weights are whole numbers that add up to 100")
        unknown = set(data.seniority) - level_keys
        if unknown:
            raise PresetError(f"{path.name}: seniority: no level called {', '.join(sorted(unknown))}")
        roles = []
        for role in data.roles:
            if any(role.key == r.key for r in roles):
                raise PresetError(f"{path.name}: role {role.key!r} is listed twice")
            roles.append(Role(role.key, role.label, _phrases(path, f"{role.key}.titles", role.titles),
                              _phrases(path, f"{role.key}.exclude", role.exclude),
                              _unique(path, f"{role.key}.search", role.search)))
        industries.append(Industry(
            key=_stem(path), label=data.label, description=data.description,
            skills=_unique(path, "skills", data.skills), scoring=dict(data.scoring),
            seniority={k: _phrases(path, f"seniority.{k}", v) for k, v in data.seniority.items()},
            roles=tuple(roles),
        ))

    arrangement_keys = {key for key, _ in ARRANGEMENTS}
    period_keys = {key for key, _ in SALARY_PERIODS}
    markets = []
    for path in sorted((root / "markets").glob("*.toml")):
        data = _read(path, MarketFile)
        if data.salary_period not in period_keys:
            raise PresetError(f"{path.name}: salary_period is one of {', '.join(sorted(period_keys))}")
        if set(data.arrangements) - arrangement_keys:
            raise PresetError(f"{path.name}: arrangements are from {', '.join(sorted(arrangement_keys))}")
        markets.append(Market(
            key=_stem(path), label=data.label, currency=data.currency, salary_period=data.salary_period,
            locations=_unique(path, "locations", data.locations), arrangements=tuple(data.arrangements),
            countries=dict(data.countries),
        ))
    if not industries or not markets:
        raise PresetError(f"{root}: at least one industry and one market are needed")

    countries: dict[str, str] = {}
    for market in markets:
        for code, name in market.countries.items():
            if countries.setdefault(code, name) != name:
                raise PresetError(f"{market.key}.toml: {code} is called {countries[code]!r} in another market")
    return Catalog(
        industries={i.key: i for i in sorted(industries, key=lambda i: i.label.casefold())},
        markets={m.key: m for m in sorted(markets, key=lambda m: m.label.casefold())},
        levels=tuple(levels),
        dimensions=dimensions,
        bands=tuple(Band(b.min, b.label, b.advice) for b in scoring.bands),
        countries=dict(sorted(countries.items(), key=lambda item: item[1])),
        currencies=tuple(sorted({m.currency for m in markets})),
    )


def presets_dir() -> Path:
    """PRESETS_DIR, or the nearest presets/ folder above this file (the repo's
    in development, /app/presets in the Docker image)."""
    configured = get_settings().presets_dir
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        if (parent / "presets" / "industries").is_dir():
            return parent / "presets"
    raise PresetError("No presets/ folder found - set PRESETS_DIR")


@lru_cache
def get_catalog() -> Catalog:
    return load_catalog(presets_dir())
