"""The industry and market presets (presets/ at the repo root), loaded and
checked once. See presets/README.md for the file format."""

from app.presets.catalog import (
    ARRANGEMENTS,
    LANGUAGE_LEVELS,
    SALARY_PERIODS,
    Catalog,
    PresetError,
    get_catalog,
    load_catalog,
)

__all__ = [
    "ARRANGEMENTS",
    "LANGUAGE_LEVELS",
    "SALARY_PERIODS",
    "Catalog",
    "PresetError",
    "get_catalog",
    "load_catalog",
]
