"""The signed-in user's applications: list, add, update, history, CSV."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import applications as service
from app.auth import current_user
from app.db.models import ACTIVE_STATUSES, Application, User
from app.db.session import get_db
from app.schemas.applications import (
    STATUS_KEYS,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationList,
    ApplicationPatch,
    ApplicationRead,
)

router = APIRouter(prefix="/applications", tags=["applications"])

View = Literal["active", "closed", "all", *STATUS_KEYS]  # type: ignore[valid-type]


@router.get("", response_model=ApplicationList)
def list_applications(view: View = "active", sort: Literal["updated", "next_step"] = "updated",
                      q: str = Query("", max_length=100), limit: int = 100, offset: int = 0,
                      user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """sort=next_step: the soonest next steps first, then those without one."""
    mine = select(Application).where(Application.user_id == user.id)
    if view == "active":
        mine = mine.where(Application.status.in_(ACTIVE_STATUSES))
    elif view == "closed":
        mine = mine.where(Application.status.not_in(ACTIVE_STATUSES))
    elif view != "all":
        mine = mine.where(Application.status == view)
    if q.strip():
        like = f"%{q.strip()}%"
        mine = mine.where(or_(Application.title.ilike(like), Application.company.ilike(like),
                              Application.notes.ilike(like)))
    total = db.scalar(select(func.count()).select_from(mine.subquery()))
    order = [Application.updated_at.desc(), Application.id]
    if sort == "next_step":
        order = [Application.next_step_on.is_(None), Application.next_step_on, *order]
    items = list(db.scalars(mine.order_by(*order).limit(min(max(limit, 1), 500)).offset(max(offset, 0))))
    closed = service.job_closed(db, items)
    return {"items": [service.read(a, closed) for a in items], "total": total, "counts": service.counts(db, user)}


@router.post("", response_model=ApplicationRead, status_code=201)
def create_application(payload: ApplicationCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    try:
        application = service.create(db, user, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="No such job.") from exc
    except service.AlreadyTracked as exc:
        raise HTTPException(status_code=409, detail="This job already has an application.") from exc
    db.commit()
    return service.read(application, service.job_closed(db, [application]))


@router.get("/export.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def export_csv(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    name = f"job-hunter-applications-{dt.date.today().isoformat()}.csv"
    return Response(service.to_csv(db, user), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"})


def _mine(db: Session, user: User, application_id: str) -> Application:
    application = db.get(Application, application_id)
    if application is None or application.user_id != user.id:
        raise HTTPException(status_code=404, detail="No such application.")
    return application


def _detail(db: Session, application: Application) -> dict:
    return {**service.read(application, service.job_closed(db, [application])), "events": application.events}


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _detail(db, _mine(db, user, application_id))


@router.patch("/{application_id}", response_model=ApplicationDetail)
def patch_application(application_id: str, payload: ApplicationPatch, user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> dict:
    application = service.update(_mine(db, user, application_id), payload)
    db.commit()
    return _detail(db, application)


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(_mine(db, user, application_id))
    db.commit()
    return Response(status_code=204)
