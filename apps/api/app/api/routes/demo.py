"""Demo mode (app/demo.py): who you can try Job Hunter as, and setting up a
new demo account as one of them."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import demo
from app.auth import current_user
from app.config import get_settings
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/demo", tags=["demo"])


class SeedWrite(BaseModel):
    person: str


@router.get("")
def get_demo() -> dict:
    """Public: whether this is a demo site, and its fictional people."""
    settings = get_settings()
    return {"enabled": settings.demo_mode, "account_hours": settings.demo_account_hours,
            "people": demo.people() if settings.demo_mode else []}


@router.post("/seed", status_code=204)
def seed(payload: SeedWrite, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    """Sets up the caller - a brand-new demo account - as a demo person."""
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="This isn't a demo site.")
    if demo.recent_accounts(db, dt.datetime.now(dt.UTC)) > settings.demo_accounts_per_hour:
        raise HTTPException(status_code=429, detail="The demo is busy - try again in a few minutes.")
    try:
        demo.seed(db, user, payload.person, settings=settings)
    except demo.DemoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
