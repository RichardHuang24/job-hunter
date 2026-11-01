"""The admin page's data - for ADMIN_EMAILS only (app/admin.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import admin
from app.auth import admin_user
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_user)])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)) -> dict:
    """People, AI costs per person this month, each job source's error rate
    over 7 days, and the task queue."""
    return admin.overview(db)
