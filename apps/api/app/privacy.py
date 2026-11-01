"""People's rights over their data (UK GDPR): a copy of everything kept
about them, and deleting their account with all of it. Also the facts the
privacy page states about this deployment.

The export is a ZIP: data.json (every row kept about the person, in full),
applications.csv, their CV PDFs, and a README. Secrets are left out - sign-in
tokens and sessions - since they're only ever ours to check.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
import re
import zipfile
from typing import Any

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app import applications
from app.config import Settings, get_settings
from app.db.models import (
    Account,
    AiUsage,
    Application,
    Cv,
    Document,
    Job,
    JobScore,
    Profile,
    ProfileTarget,
    SavedSearch,
    SearchRun,
    User,
    UserJob,
    VerificationToken,
)
from app.scoring.providers import describe
from app.sources import enabled_sources
from app.storage import StorageError, get_storage

log = logging.getLogger("job_hunter.privacy")

SECRET_COLUMNS = {"refresh_token", "access_token", "id_token", "session_state"}  # OAuth tokens: never exported
README = """Your data from Job Hunter
=========================

Exported {when} for {email}.

data.json         Everything Job Hunter keeps about you: your account,
                  profile, target roles, saved searches and their runs, the
                  jobs found for you with their checks and AI scores, your
                  AI usage, applications and their history, and your CV.
applications.csv  Your applications, as in the Applications page's export.
cv/               The CV PDFs you've made that are still kept.

Left out: sign-in secrets (session and login tokens). Jobs are shared
postings from job boards; each comes with what you made of it.
"""


def _row(obj: Any, drop: set[str] = frozenset()) -> dict:
    """Every column of a row, by attribute name, minus `drop`."""
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs
            if attr.key not in drop and attr.key not in SECRET_COLUMNS}


def _json(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    raise TypeError(f"Can't export {type(value).__name__}")


def collect(db: Session, user: User) -> dict:
    """Everything kept about this person."""
    uid = user.id
    jobs = db.execute(select(UserJob, Job, JobScore).join(Job, UserJob.job_id == Job.id)
                      .outerjoin(JobScore, JobScore.user_job_id == UserJob.id).where(UserJob.user_id == uid)
                      .order_by(UserJob.first_seen_at)).all()
    apps = db.scalars(select(Application).where(Application.user_id == uid).order_by(Application.created_at)).all()
    cv = db.get(Cv, uid)
    return {
        "exported_at": dt.datetime.now(dt.UTC),
        "account": {**_row(user), "sign_in_with": [a.provider for a in db.scalars(select(Account).where(Account.user_id == uid))]},
        "profile": _row(db.get(Profile, uid), {"user_id"}) if db.get(Profile, uid) else None,
        "target_roles": [_row(t, {"user_id"}) for t in db.scalars(select(ProfileTarget).where(ProfileTarget.user_id == uid))],
        "saved_searches": [_row(s, {"user_id"}) for s in db.scalars(select(SavedSearch).where(SavedSearch.user_id == uid))],
        "search_runs": [_row(r, {"user_id", "task_id"}) for r in db.scalars(select(SearchRun).where(SearchRun.user_id == uid))],
        "jobs": [{**_row(uj, {"user_id", "job_id"}),
                  "job": _row(job, {"fingerprint", "checked_at"}),
                  "ai_score": _row(score, {"user_id", "user_job_id"}) if score else None} for uj, job, score in jobs],
        "ai_usage": [_row(u, {"user_id"}) for u in db.scalars(select(AiUsage).where(AiUsage.user_id == uid))],
        "applications": [{**_row(a, {"user_id"}), "history": [_row(e, {"user_id", "application_id"}) for e in a.events]}
                         for a in apps],
        "cv": cv.content if cv else None,
        "documents": [_row(d, {"user_id", "storage_key"}) for d in db.scalars(select(Document).where(Document.user_id == uid))],
    }


def _pdf_name(document: Document, taken: set[str]) -> str:
    base = re.sub(r"[^\w .()-]+", "", document.filename.removesuffix(".pdf")).strip() or "CV"
    stamp = (document.finished_at or document.requested_at).strftime("%Y-%m-%d %H%M")
    name = f"cv/{base} ({stamp}).pdf"
    while name in taken:
        name = name.removesuffix(".pdf") + "-1.pdf"
    taken.add(name)
    return name


def export_zip(db: Session, user: User) -> bytes:
    data = collect(db, user)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", README.format(when=data["exported_at"].strftime("%d %B %Y, %H:%M UTC"),
                                                     email=user.email or "you"))
        archive.writestr("applications.csv", applications.to_csv(db, user))
        taken: set[str] = set()
        missing = []
        for document in db.scalars(select(Document).where(Document.user_id == user.id, Document.status == "done")):
            try:
                archive.writestr(_pdf_name(document, taken), get_storage().get(document.storage_key))
            except StorageError:
                missing.append(document.id)
        if missing:
            data["documents_missing_from_storage"] = missing
        archive.writestr("data.json", json.dumps(data, default=_json, indent=2, ensure_ascii=False))
    return out.getvalue()


def delete_account(db: Session, user: User) -> dict:
    """Deletes the person and everything that's theirs: their files in
    storage first, then their rows - the database cascades from users to
    every table that holds a user_id. Shared job postings stay."""
    files = removed = 0
    for key in db.scalars(select(Document.storage_key).where(Document.user_id == user.id, Document.storage_key != "")):
        files += 1
        try:
            get_storage().delete(key)
            removed += 1
        except StorageError as exc:
            log.warning("Couldn't delete a file of a deleted account: %s", exc)
    email = user.email
    db.delete(user)
    if email:
        db.execute(delete(VerificationToken).where(VerificationToken.identifier == email))
    db.commit()
    log.info("Deleted an account and %d of its %d files", removed, files)
    return {"files": files, "files_deleted": removed}


def facts(settings: Settings | None = None) -> dict:
    """What the privacy page says about this deployment."""
    settings = settings or get_settings()
    ai = describe(settings)
    if settings.storage_backend == "s3" and settings.s3_endpoint_url and "storage:" not in settings.s3_endpoint_url:
        storage = re.sub(r"^https?://", "", settings.s3_endpoint_url).split("/")[0]
    elif settings.storage_backend == "s3" and not settings.s3_endpoint_url:
        storage = "Amazon S3"
    else:
        storage = ""  # on this server
    return {
        "controller": settings.privacy_controller, "contact": settings.privacy_contact,
        "configured": bool(settings.privacy_controller and settings.privacy_contact),
        "ai_provider": ai["provider"], "ai_model": ai["model"],
        "sources": [{"label": s.label, "homepage": s.homepage} for s in enabled_sources(settings) if not s.demo],
        "storage": storage, "billing": settings.billing_enabled, "cv_files_kept": settings.cv_files_kept,
    }
