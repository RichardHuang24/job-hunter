"""CVs and the documents made from them."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.cv.schema import CvContent
from app.schemas.me import UtcDatetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str  # cv
    status: str  # queued, done, failed
    filename: str
    size_bytes: int
    pages: int
    error: str
    requested_at: UtcDatetime
    finished_at: UtcDatetime | None


class CvRead(BaseModel):
    content: CvContent
    saved: bool  # false: not saved yet, so made from the profile
    updated_at: UtcDatetime | None
    documents: list[DocumentRead]  # the latest first


class BillingRead(BaseModel):
    enabled: bool  # false: every feature is free (the self-hosted default)
    configured: bool  # the Stripe keys are set
