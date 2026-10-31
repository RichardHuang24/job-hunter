"""The signed-in user's CV, and the PDFs made from it."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.cv import service
from app.cv.schema import CvContent
from app.db.models import Document, User
from app.db.session import get_db
from app.schemas.cv import CvRead, DocumentRead
from app.storage import StorageError, get_storage

router = APIRouter(tags=["cv"])

RECENT = 10


def _documents(db: Session, user: User) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.user_id == user.id, Document.kind == "cv")
                           .order_by(Document.requested_at.desc(), Document.id).limit(RECENT)))


def _read(db: Session, user: User) -> dict:
    content, saved = service.current(db, user)
    return {"content": content, "saved": saved is not None, "updated_at": saved.updated_at if saved else None,
            "documents": _documents(db, user)}


@router.get("/cv", response_model=CvRead)
def get_cv(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """The CV - or, until it's saved, one made from the profile (saved: false)."""
    return _read(db, user)


@router.put("/cv", response_model=CvRead)
def put_cv(content: CvContent, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    service.save(db, user, content)
    db.commit()
    return _read(db, user)


@router.post("/cv/pdf", response_model=DocumentRead, status_code=202)
def make_pdf(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Document:
    """Queues a PDF of the saved CV; the worker builds it. Poll
    GET /documents/{id} until status isn't "queued"."""
    try:
        document = service.queue_pdf(db, user)
    except service.AlreadyBuilding as exc:
        raise HTTPException(status_code=409, detail="A PDF is already being made.") from exc
    db.commit()
    return document


def _mine(db: Session, user: User, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="No such document.")
    return document


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Document:
    return _mine(db, user, document_id)


@router.get("/documents/{document_id}/file", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def get_file(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    document = _mine(db, user, document_id)
    if document.status != "done":
        raise HTTPException(status_code=409, detail="This document isn't ready.")
    try:
        data = get_storage().get(document.storage_key)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail="The file couldn't be read from storage.") from exc
    plain = document.filename.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return Response(data, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=\"{plain}\"; filename*=UTF-8''{quote(document.filename)}",
        "Cache-Control": "private, no-store",
    })


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    document = _mine(db, user, document_id)
    if document.status == "queued":
        raise HTTPException(status_code=409, detail="It's still being made.")
    service.delete(db, document)
    db.commit()
    return Response(status_code=204)
