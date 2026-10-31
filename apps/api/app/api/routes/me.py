"""The signed-in user: their profile, the roles they're after, onboarding,
and checking how a job title would be read."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import profiles
from app.db.models import SavedSearch
from app.db.models import Profile, User
from app.db.session import get_db
from app.matching.titles import match_title
from app.presets import get_catalog
from app.search import runs
from app.search.matching import rematch
from app.search.schedule import EVERY
from app.config import get_settings
from app.schemas.jobs import AiStatus
from app.scoring import providers as scorers
from app.scoring import service as scoring
from app.schemas.me import (
    MeRead,
    OnboardingWrite,
    ProfileRead,
    ProfileWrite,
    TargetList,
    TargetRead,
    TitleCheckRead,
    TitleCheckWrite,
)

router = APIRouter(prefix="/me", tags=["me"])


def _me(user: User) -> MeRead:
    return MeRead(
        id=user.id, email=user.email, name=user.name,
        profile=ProfileRead.model_validate(user.profile) if user.profile else None,
        targets=[TargetRead.model_validate(t) for t in user.targets],
    )


@router.get("", response_model=MeRead)
def get_me(user: User = Depends(current_user)) -> MeRead:
    return _me(user)


@router.put("/profile", response_model=ProfileRead)
def put_profile(payload: ProfileWrite, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Profile:
    profile = profiles.save_profile(db, user, payload)
    db.flush()
    rematch(db, user)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/targets", response_model=list[TargetRead])
def put_targets(payload: TargetList, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    """Every target role, in order - ones left out are deleted."""
    targets = profiles.replace_targets(db, user, payload)
    rematch(db, user)
    db.commit()
    return targets


@router.post("/onboarding", response_model=MeRead)
def post_onboarding(payload: OnboardingWrite, user: User = Depends(current_user), db: Session = Depends(get_db)) -> MeRead:
    """First-run setup: saves the profile and replaces the target roles with
    the chosen preset roles plus any custom ones. The first time, it also
    makes a saved search from the profile and runs it."""
    industry = get_catalog().industries[payload.industry]
    profile = profiles.save_profile(db, user, payload)
    profiles.replace_targets(db, user, profiles.preset_targets(industry, payload.roles) + payload.custom_roles)
    profiles.finish_onboarding(profile)
    rematch(db, user)
    if not user.searches:
        now = dt.datetime.now(dt.UTC)
        search = SavedSearch(user_id=user.id, created_at=now, updated_at=now, next_run_at=now + EVERY,
                             **runs.suggestion(user))
        user.searches.append(search)
        db.flush()
        runs.start_run(db, search, trigger="onboarding")
    db.commit()
    db.refresh(user)
    return _me(user)


def _list(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]


@router.post("/title-check", response_model=TitleCheckRead)
def post_title_check(payload: TitleCheckWrite, user: User = Depends(current_user)) -> TitleCheckRead:
    """How a job title would be read against this user's target roles and
    seniority - the same rules job search will apply."""
    catalog = get_catalog()
    industry = user.profile.industry if user.profile else ""
    wanted_levels = user.profile.seniority_levels if user.profile else []
    result = match_title(payload.title, user.targets, catalog.levels_for(industry))
    labels = {lv.key: lv.label for lv in catalog.levels}
    level_label = labels.get(result.level, result.level)
    wanted = result.target is not None and (not wanted_levels or result.level in wanted_levels)

    if result.target is None:
        explanation = "Doesn't match any of your target roles."
    elif wanted:
        explanation = f"Counts as {result.target.label} (matched “{result.phrase}”), at {level_label.lower()} level."
    else:
        explanation = (f"Counts as {result.target.label}, but it reads as {level_label.lower()} and you're after "
                       f"{_list([labels.get(k, k).lower() for k in wanted_levels])}.")
    return TitleCheckRead(
        title=payload.title,
        target=TargetRead.model_validate(result.target) if result.target is not None else None,
        matched=result.phrase,
        level={"key": result.level, "label": level_label},
        level_words=list(result.level_words),
        wanted=wanted,
        explanation=explanation,
    )


@router.get("/ai", response_model=AiStatus)
def get_ai(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Which scorer this deployment uses, and this user's allowance this month."""
    settings = get_settings()
    used, spent = scoring.usage_this_month(db, user.id)
    return {**scorers.describe(settings), "auto_score": settings.ai_auto_score,
            "month": dt.datetime.now(dt.UTC).strftime("%Y-%m"), "scores_used": used,
            "scores_limit": settings.ai_scores_per_month, "queued": scoring.queued_count(db, user.id),
            "cost_usd": round(spent, 4), "budget_usd": settings.ai_budget_usd_per_month}
