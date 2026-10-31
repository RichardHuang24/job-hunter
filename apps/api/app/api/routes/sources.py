"""The job sources this deployment uses (app/sources)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import current_user
from app.schemas.search import SourceRead
from app.sources import enabled_sources

router = APIRouter(prefix="/sources", tags=["searches"], dependencies=[Depends(current_user)])


@router.get("", response_model=list[SourceRead])
def get_sources() -> list[dict]:
    return [{"key": s.key, "label": s.label, "description": s.description, "homepage": s.homepage,
             "countries": list(s.countries), "commercial": s.commercial, "demo": s.demo}
            for s in enabled_sources()]
