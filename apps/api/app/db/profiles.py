"""Writing a user's profile and target roles."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.db.models import Profile, ProfileTarget, User
from app.presets.catalog import Industry
from app.schemas.me import ProfileFields, TargetWrite


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def save_profile(db: Session, user: User, payload: ProfileFields) -> Profile:
    profile = user.profile or Profile(user_id=user.id)
    data = payload.model_dump(include=set(ProfileFields.model_fields))
    for name, value in data.items():
        setattr(profile, name, value)
    profile.updated_at = _now()
    db.add(profile)
    user.profile = profile
    return profile


def replace_targets(db: Session, user: User, targets: list[TargetWrite]) -> list[ProfileTarget]:
    """Every target, in order - ones left out are deleted."""
    user.targets.clear()
    db.flush()
    now = _now()
    for position, target in enumerate(targets):
        user.targets.append(ProfileTarget(position=position, created_at=now, updated_at=now, **target.model_dump()))
    db.flush()
    return user.targets


def preset_targets(industry: Industry, role_keys: list[str]) -> list[TargetWrite]:
    """Targets made from an industry's preset roles, in the order chosen."""
    out = []
    for key in dict.fromkeys(role_keys):
        role = industry.role(key)
        if role is not None:
            out.append(TargetWrite(label=role.label, titles=list(role.titles), exclude=list(role.exclude),
                                   search=list(role.search), preset_role=f"{industry.key}/{role.key}"))
    return out


def finish_onboarding(profile: Profile) -> None:
    if profile.onboarded_at is None:
        profile.onboarded_at = _now()
