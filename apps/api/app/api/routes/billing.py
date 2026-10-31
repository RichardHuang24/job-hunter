"""Billing: whether it's on, and Stripe's webhook (app/billing.py).

The webhook is the one route that doesn't take a signed-in user's token:
Stripe calls it directly (through Caddy in production), and the Stripe
signature is what's checked instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import billing
from app.auth import current_user
from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.cv import BillingRead

router = APIRouter(prefix="/billing", tags=["billing"])

MAX_EVENT_BYTES = 512 * 1024


@router.get("", response_model=BillingRead)
def get_billing(user: User = Depends(current_user)) -> dict:
    return billing.status()


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.billing_enabled:
        raise HTTPException(status_code=404, detail="Billing is off.")
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET isn't set.")
    payload = await request.body()
    if len(payload) > MAX_EVENT_BYTES:
        raise HTTPException(status_code=413, detail="Too large for a Stripe event.")
    try:
        event = billing.verify(payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
    except billing.BadSignature as exc:
        raise HTTPException(status_code=400, detail="The Stripe signature doesn't match.") from exc
    recorded = await run_in_threadpool(billing.record, db, event)  # the database is synchronous
    return {"received": True, "duplicate": not recorded}
