"""The signed-in user and their profile."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db.models import Profile, User
from app.db.session import get_db
from app.schemas.me import MeRead, ProfileRead, ProfileWrite

router = APIRouter(prefix="/me", tags=["me"])


def _me(user: User) -> MeRead:
    profile = ProfileRead.model_validate(user.profile) if user.profile else None
    return MeRead(id=user.id, email=user.email, name=user.name, profile=profile)


@router.get("", response_model=MeRead)
def get_me(user: User = Depends(current_user)) -> MeRead:
    return _me(user)


@router.put("/profile", response_model=ProfileRead)
def put_profile(payload: ProfileWrite, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Profile:
    profile = user.profile or Profile(user_id=user.id)
    for name, value in payload.model_dump().items():
        setattr(profile, name, value)
    profile.updated_at = dt.datetime.now(dt.UTC)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
