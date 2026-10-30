"""The choices the profile form offers - see app/presets.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import current_user
from app.presets import INDUSTRIES, MARKETS
from app.schemas.me import PresetsRead

router = APIRouter(prefix="/presets", tags=["presets"], dependencies=[Depends(current_user)])


@router.get("", response_model=PresetsRead)
def get_presets() -> dict:
    return {
        "industries": [{"key": key, "label": label} for key, label in INDUSTRIES],
        "markets": [{"key": key, "label": label} for key, label in MARKETS],
    }
