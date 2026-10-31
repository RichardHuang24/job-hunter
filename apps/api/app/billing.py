"""Billing with Stripe - the switch and the webhook so far.

BILLING_ENABLED=false (the default, and the self-hosted setup): every feature
is free and nothing here runs. When it's on, Stripe sends events to
POST /billing/webhook; each is checked against STRIPE_WEBHOOK_SECRET and
recorded once in billing_events. Plans, checkout and limits per plan come
with the hosted version (docs/roadmap.md) - the events are kept so they can
be applied then.
"""

from __future__ import annotations

import json
import logging

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import BillingEvent

log = logging.getLogger("job_hunter.billing")


class BadSignature(ValueError):
    pass


def status(settings: Settings | None = None) -> dict[str, bool]:
    settings = settings or get_settings()
    return {"enabled": settings.billing_enabled,
            "configured": bool(settings.stripe_secret_key and settings.stripe_webhook_secret)}


def verify(payload: bytes, signature: str, secret: str) -> dict:
    """The event, if Stripe signed it with this secret in the last five minutes."""
    try:
        stripe.Webhook.construct_event(payload, signature, secret)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise BadSignature(str(exc)) from exc
    event = json.loads(payload)
    if not isinstance(event, dict) or not str(event.get("id", "")).startswith("evt_"):
        raise BadSignature("Not a Stripe event.")
    return event


def record(db: Session, event: dict) -> bool:
    """Keeps the event; False if it was already kept (Stripe resends)."""
    if db.get(BillingEvent, event["id"]) is not None:
        return False
    db.add(BillingEvent(id=event["id"], type=str(event.get("type", ""))[:100], livemode=bool(event.get("livemode")),
                        payload=event))
    try:
        db.commit()
    except IntegrityError:  # the same event, arriving twice at once
        db.rollback()
        return False
    log.info("Stripe event %s (%s) recorded", event["id"], event.get("type"))
    return True
