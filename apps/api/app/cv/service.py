"""Each person's CV, and turning it into a PDF on the worker.

Until someone saves their CV, it starts from their profile: name, headline,
email, summary, skills and languages. A PDF is a Document: queued here,
built by the worker's "cv_pdf" task, kept in storage, and the oldest beyond
CV_FILES_KEPT deleted.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.cv.build import BuildError, build_pdf
from app.cv.latex import render
from app.cv.schema import CvContent
from app.db.models import Cv, Document, User
from app.matching.evaluate import is_remote_place
from app.presets import get_catalog
from app.storage import StorageError, get_storage
from app.tasks import queue

log = logging.getLogger("job_hunter.cv")


class AlreadyBuilding(RuntimeError):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def from_profile(user: User) -> CvContent:
    profile = user.profile
    if profile is None:
        return CvContent(name=user.name or "", email=user.email or "")
    place = next((p for p in profile.locations if not is_remote_place(p)), "")
    return CvContent.model_validate({
        "name": profile.display_name or user.name or "", "headline": profile.headline, "email": user.email or "",
        "location": place, "summary": profile.summary[:1200], "skills": profile.skills[:40],
        "languages": profile.languages[:10],
    })


def current(db: Session, user: User) -> tuple[CvContent, Cv | None]:
    """The saved CV, or one made from the profile if there isn't one yet."""
    saved = db.get(Cv, user.id)
    return (CvContent.model_validate(saved.content) if saved else from_profile(user)), saved


def save(db: Session, user: User, content: CvContent) -> Cv:
    cv = db.get(Cv, user.id)
    if cv is None:
        cv = Cv(user_id=user.id)
        db.add(cv)
    cv.content = content.model_dump()
    cv.updated_at = _now()
    return cv


def filename(content: CvContent) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "", content.name).strip()
    return f"CV - {name}.pdf" if name else "CV.pdf"


def queue_pdf(db: Session, user: User) -> Document:
    """Queues a PDF of the current CV. One at a time per person."""
    building = db.scalar(select(Document.id).where(Document.user_id == user.id, Document.status == "queued").limit(1))
    if building is not None:
        raise AlreadyBuilding()
    content, _ = current(db, user)
    document = Document(user_id=user.id, kind="cv", status="queued", filename=filename(content), requested_at=_now())
    db.add(document)
    db.flush()
    queue.enqueue(db, "cv_pdf", {"document_id": document.id}, user_id=user.id, max_attempts=1)
    return document


def storage_key(document: Document) -> str:
    return f"users/{document.user_id}/documents/{document.id}.pdf"


def _country(user: User) -> str:
    market = get_catalog().markets.get(user.profile.market) if user.profile else None
    return next(iter(market.countries)) if market and len(market.countries) == 1 else ""


def _prune(db: Session, user_id: int) -> int:
    """Deletes the oldest finished PDFs beyond CV_FILES_KEPT, files and all."""
    keep = max(1, get_settings().cv_files_kept)
    old = db.scalars(select(Document).where(Document.user_id == user_id, Document.status != "queued")
                     .order_by(Document.requested_at.desc(), Document.id).offset(keep)).all()
    for document in old:
        delete(db, document)
    return len(old)


def delete(db: Session, document: Document) -> None:
    if document.storage_key:
        try:
            get_storage().delete(document.storage_key)
        except StorageError as exc:  # the row goes anyway; an orphaned file is harmless
            log.warning("Couldn't delete %s: %s", document.storage_key, exc)
    db.delete(document)


def run_task(db: Session, document_id: str) -> dict:
    """The worker's "cv_pdf" task. A build that fails marks the document
    failed with the reason; the task itself succeeds."""
    document = db.get(Document, document_id)
    if document is None:
        raise LookupError(f"No document {document_id}")
    user = db.get(User, document.user_id)
    content, _ = current(db, user)
    try:
        pdf = build_pdf(render(content, _country(user)))
        key = storage_key(document)
        get_storage().put(key, pdf.data, "application/pdf")
    except (BuildError, StorageError) as exc:
        log.warning("CV PDF %s failed: %s", document.id, exc)
        document.status, document.error, document.finished_at = "failed", str(exc)[:1000], _now()
        db.commit()
        return {"document_id": document.id, "status": "failed"}
    document.status, document.storage_key, document.finished_at = "done", key, _now()
    document.size_bytes, document.pages, document.error = len(pdf.data), pdf.pages, ""
    db.flush()
    pruned = _prune(db, user.id)
    db.commit()
    return {"document_id": document.id, "status": "done", "pages": pdf.pages, "pruned": pruned}
