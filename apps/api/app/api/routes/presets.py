"""The choices the profile forms offer - presets/ at the repo root, loaded by
app/presets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.db.models import APPLICATION_STATUSES
from app.presets import ARRANGEMENTS, LANGUAGE_LEVELS, SALARY_PERIODS, get_catalog
from app.schemas.presets import IndustryRead, MarketRead, PresetsRead

router = APIRouter(prefix="/presets", tags=["presets"], dependencies=[Depends(current_user)])


def _options(pairs) -> list[dict]:
    return [{"key": key, "label": label} for key, label in pairs]


@router.get("", response_model=PresetsRead)
def get_presets() -> dict:
    catalog = get_catalog()
    return {
        "industries": [{"key": i.key, "label": i.label, "description": i.description} for i in catalog.industries.values()],
        "markets": [{"key": m.key, "label": m.label, "currency": m.currency} for m in catalog.markets.values()],
        "levels": [{"key": lv.key, "label": lv.label} for lv in catalog.levels],
        "arrangements": _options(ARRANGEMENTS),
        "salary_periods": _options(SALARY_PERIODS),
        "language_levels": _options(LANGUAGE_LEVELS),
        "countries": _options(catalog.countries.items()),
        "currencies": list(catalog.currencies),
        "application_statuses": _options(APPLICATION_STATUSES),
    }


@router.get("/industries/{key}", response_model=IndustryRead)
def get_industry(key: str) -> dict:
    catalog = get_catalog()
    industry = catalog.industries.get(key)
    if industry is None:
        raise HTTPException(status_code=404, detail="No such industry.")
    return {
        "key": industry.key, "label": industry.label, "description": industry.description,
        "skills": list(industry.skills),
        "roles": [{"key": r.key, "label": r.label, "titles": list(r.titles), "exclude": list(r.exclude),
                   "search": list(r.search)} for r in industry.roles],
        "scoring": [{"key": d.key, "label": d.label, "description": d.description, "weight": industry.scoring[d.key]}
                    for d in catalog.dimensions.values()],
        "seniority": {key: list(words) for key, words in industry.seniority.items()},
    }


@router.get("/markets/{key}", response_model=MarketRead)
def get_market(key: str) -> dict:
    market = get_catalog().markets.get(key)
    if market is None:
        raise HTTPException(status_code=404, detail="No such market.")
    return {
        "key": market.key, "label": market.label, "currency": market.currency,
        "salary_period": market.salary_period, "locations": list(market.locations),
        "arrangements": list(market.arrangements), "countries": _options(market.countries.items()),
    }
