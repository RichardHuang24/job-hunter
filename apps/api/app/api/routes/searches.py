"""Saved searches and their runs. Running one queues it for the worker; the
client polls the run until it's done."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db.models import SavedSearch, SearchRun, User
from app.db.session import get_db
from app.schemas.search import RunRead, SearchFields, SearchRead, SearchWrite
from app.search import runs
from app.search.schedule import EVERY

router = APIRouter(tags=["searches"])


def _search(db: Session, user: User, search_id: str) -> SavedSearch:
    search = db.get(SavedSearch, search_id)
    if search is None or search.user_id != user.id:
        raise HTTPException(status_code=404, detail="No such search.")
    return search


def _read(search: SavedSearch) -> SearchRead:
    read = SearchRead.model_validate(search)
    read.last_run = RunRead.model_validate(search.runs[0]) if search.runs else None
    return read


def _apply(search: SavedSearch, payload: SearchWrite, now: dt.datetime) -> None:
    for name, value in payload.model_dump().items():
        setattr(search, name, value)
    if search.daily and search.next_run_at is None:
        search.next_run_at = now + EVERY
    elif not search.daily:
        search.next_run_at = None
    search.updated_at = now


@router.get("/searches", response_model=list[SearchRead])
def list_searches(user: User = Depends(current_user)) -> list[SearchRead]:
    return [_read(s) for s in user.searches]


@router.get("/searches/suggestion", response_model=SearchFields)
def get_suggestion(user: User = Depends(current_user)) -> dict:
    """A search made from the profile, to start a new one from. Not checked:
    with no target roles yet, it has no terms."""
    return runs.suggestion(user)


@router.post("/searches", response_model=SearchRead, status_code=201)
def create_search(payload: SearchWrite, user: User = Depends(current_user), db: Session = Depends(get_db)) -> SearchRead:
    if len(user.searches) >= runs.MAX_SEARCHES:
        raise HTTPException(status_code=409, detail=f"You can keep {runs.MAX_SEARCHES} saved searches - delete one first.")
    now = dt.datetime.now(dt.UTC)
    search = SavedSearch(user_id=user.id, created_at=now)
    _apply(search, payload, now)
    db.add(search)
    db.commit()
    db.refresh(search)
    return _read(search)


@router.put("/searches/{search_id}", response_model=SearchRead)
def update_search(search_id: str, payload: SearchWrite, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> SearchRead:
    search = _search(db, user, search_id)
    _apply(search, payload, dt.datetime.now(dt.UTC))
    db.commit()
    db.refresh(search)
    return _read(search)


@router.delete("/searches/{search_id}", status_code=204)
def delete_search(search_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    """The search and its run history go; the jobs it found stay."""
    db.delete(_search(db, user, search_id))
    db.commit()
    return Response(status_code=204)


@router.post("/searches/{search_id}/run", response_model=RunRead, status_code=202)
def run_search(search_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> SearchRun:
    search = _search(db, user, search_id)
    if runs.active_run(db, search) is not None:
        raise HTTPException(status_code=409, detail="This search is already running.")
    run = runs.start_run(db, search, trigger="manual")
    db.commit()
    db.refresh(run)
    return run


@router.get("/searches/{search_id}/runs", response_model=list[RunRead])
def list_runs(search_id: str, limit: int = 10, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    search = _search(db, user, search_id)
    return list(db.scalars(select(SearchRun).where(SearchRun.search_id == search.id)
                           .order_by(SearchRun.created_at.desc()).limit(min(max(limit, 1), 50))))


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> SearchRun:
    run = db.get(SearchRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="No such run.")
    return run
