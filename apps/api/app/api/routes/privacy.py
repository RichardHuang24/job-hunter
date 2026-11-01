"""What the privacy page says about this deployment (app/privacy.py). No
sign-in needed: the page is public, and nothing here is about a person."""

from __future__ import annotations

from fastapi import APIRouter

from app import privacy

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("")
def get_privacy_facts() -> dict:
    return privacy.facts()
