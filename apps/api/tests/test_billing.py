"""Billing: off by default; when on, Stripe's webhook takes only signed
events, and keeps each one once."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from app.config import get_settings
from app.db.models import BillingEvent
from tests.conftest import auth

SECRET = "whsec_test_" + "x" * 24


def signed(event: dict, secret: str = SECRET, at: int | None = None) -> tuple[bytes, str]:
    """A payload and Stripe-Signature header, made the way Stripe makes them."""
    payload = json.dumps(event).encode()
    at = int(time.time()) if at is None else at
    digest = hmac.new(secret.encode(), f"{at}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, f"t={at},v1={digest}"


EVENT = {"id": "evt_test_1", "object": "event", "type": "customer.subscription.created", "livemode": False,
         "data": {"object": {"id": "sub_1"}}}


@pytest.fixture()
def billing_on(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "x" * 24)
    get_settings.cache_clear()


def post(client, payload: bytes, signature: str):
    return client.post("/billing/webhook", content=payload, headers={"stripe-signature": signature,
                                                                     "content-type": "application/json"})


def test_billing_is_off_by_default(client, user):
    assert client.get("/billing", headers=auth(user.id)).json() == {"enabled": False, "configured": False}
    assert client.get("/billing").status_code == 401
    assert post(client, *signed(EVENT)).status_code == 404  # nothing listens


def test_signed_events_are_kept_once(client, sessions, billing_on):
    first = post(client, *signed(EVENT))
    assert first.status_code == 200 and first.json() == {"received": True, "duplicate": False}
    assert post(client, *signed(EVENT)).json() == {"received": True, "duplicate": True}  # Stripe resends
    with sessions() as session:
        [event] = session.query(BillingEvent).all()
        assert (event.id, event.type, event.livemode, event.payload["data"]["object"]["id"]) == (
            "evt_test_1", "customer.subscription.created", False, "sub_1")


def test_unsigned_or_stale_events_are_refused(client, sessions, billing_on):
    payload, _ = signed(EVENT)
    assert post(client, payload, "").status_code == 400
    assert post(client, *signed(EVENT, secret="whsec_wrong")).status_code == 400
    assert post(client, *signed(EVENT, at=int(time.time()) - 3600)).status_code == 400  # an old replay
    tampered, header = signed(EVENT)
    assert post(client, tampered.replace(b"sub_1", b"sub_2"), header).status_code == 400
    assert post(client, *signed({"id": "not-an-event"})).status_code == 400
    with sessions() as session:
        assert session.query(BillingEvent).count() == 0


def test_on_without_a_webhook_secret(client, monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    get_settings.cache_clear()
    assert post(client, *signed(EVENT)).status_code == 503


def test_billing_status_when_on(client, user, billing_on):
    assert client.get("/billing", headers=auth(user.id)).json() == {"enabled": True, "configured": True}
