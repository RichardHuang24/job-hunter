"""Demo mode (DEMO_MODE=true): a public site anyone can try without signing up.

The sign-in page offers three fictional people. Choosing one makes a fresh
account just for that visitor (an address at demo.invalid, which can't
receive email), set up as that person: profile and target roles, a search
already run against the built-in sample jobs and scored, a CV with a PDF on
the way, a saved job, and applications at different stages with their
history. Every demo account is deleted, files and all, DEMO_ACCOUNT_HOURS
(24) after it was made - the worker checks every minute.

The web app makes the account and its session (apps/web/src/app/demo);
seed() fills it in. Everyone, everything and every company here is made up.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import applications, privacy
from app.config import Settings, get_settings
from app.cv import service as cv_service
from app.cv.schema import CvContent
from app.db import profiles
from app.db.models import ApplicationEvent, Job, SavedSearch, SearchRun, Task, User, UserJob
from app.presets import get_catalog
from app.schemas.applications import ApplicationCreate
from app.schemas.me import OnboardingWrite
from app.scoring import service as scoring
from app.scoring.providers import NotConfigured, get_scorer
from app.search import runs
from app.search.schedule import EVERY
from app.tasks import queue

log = logging.getLogger("job_hunter.demo")

EMAIL_DOMAIN = "demo.invalid"  # RFC 2606: a domain that can never receive mail


def is_demo_user(user: User) -> bool:
    return bool(user.email) and user.email.endswith("@" + EMAIL_DOMAIN)


@dataclass(frozen=True)
class Tracked:
    """An application to make: for one of the person's jobs (title) or by hand (company given)."""

    title: str
    status: str
    applied_days_ago: int | None = None
    next_step: str = ""
    next_in_days: int | None = None
    notes: str = ""
    company: str = ""  # set: added by hand, not from the jobs
    location: str = ""
    history: tuple[tuple[str, int], ...] = ()  # (status, days ago), oldest first, after "created"


@dataclass(frozen=True)
class DemoPerson:
    key: str
    name: str
    headline: str
    description: str  # one line on the sign-in page
    onboarding: dict
    cv: dict
    saved: tuple[str, ...] = ()
    tracked: tuple[Tracked, ...] = field(default_factory=tuple)


PEOPLE: dict[str, DemoPerson] = {p.key: p for p in (
    DemoPerson(
        key="nurse", name="Jo Example", headline="Registered nurse",
        description="A ward nurse in Manchester, after a step up to Band 6.",
        onboarding={
            "display_name": "Jo Example", "headline": "Registered nurse", "industry": "healthcare", "market": "uk",
            "summary": "Ward nurse with four years in acute medicine, looking for a Band 6 role or a move into research nursing.",
            "years_experience": 4, "roles": ["registered-nurse"],
            "custom_roles": [{"label": "Research nurse", "titles": ["research nurse"]}],
            "seniority_levels": ["mid", "senior"], "locations": ["Manchester"], "work_arrangements": ["onsite", "hybrid"],
            "authorized_countries": ["GB"], "salary_min": 32000, "salary_currency": "GBP",
            "skills": ["Patient assessment", "Medication administration", "Care planning", "Wound care", "Clinical documentation"],
            "languages": [{"name": "English", "level": "native"}, {"name": "Spanish", "level": "conversational"}],
        },
        cv={
            "links": [], "phone": "+44 7700 900461",  # Ofcom's range for fiction - public-data: ok
            "experience": [
                {"title": "Staff Nurse - Acute Medicine", "employer": "Northwind Health NHS Trust", "location": "Manchester",
                 "start": "Sep 2022", "bullets": ["Cared for up to 8 patients a shift on a 28-bed acute medical ward",
                                                  "Led a ward project that cut medication errors by 30% in six months",
                                                  "Mentored four newly qualified nurses through preceptorship"]},
                {"title": "Healthcare Assistant", "employer": "Lucerne Care Homes", "location": "Stockport",
                 "start": "2019", "end": "2022", "bullets": ["Supported residents with personal care and daily living",
                                                             "Took observations and escalated changes to the nurse in charge"]},
            ],
            "education": [{"qualification": "BSc (Hons) Adult Nursing", "institution": "University of Manchester",
                           "start": "2019", "end": "2022", "details": "NMC registered"}],
        },
        saved=("Staff Nurse - Acute Medicine",),
        tracked=(
            Tracked("Senior Staff Nurse - Band 6", "interviewing", 9, "Panel interview with the ward manager", 2,
                    "Prepare a story about the medication errors project.", history=(("applied", 9), ("interviewing", 3))),
            Tracked("Research Nurse", "applied", 4, "Chase if no reply", 10),
            Tracked("Registered Nurse - Day Surgery", "planned", None, "Ask a friend there about the team", 1),
            Tracked("Practice Nurse", "rejected", 21, company="Riverside Surgery", location="Salford",
                    notes="They wanted two years in general practice.", history=(("applied", 21), ("rejected", 12))),
        ),
    ),
    DemoPerson(
        key="analyst", name="Sam Example", headline="Data analyst",
        description="A data analyst in Leeds, open to remote work.",
        onboarding={
            "display_name": "Sam Example", "headline": "Data analyst", "industry": "data-ai", "market": "uk",
            "summary": "Data analyst who turns messy data into dashboards and decisions; looking at analyst and junior data science roles.",
            "years_experience": 3, "roles": ["data-analyst", "data-scientist"],
            "seniority_levels": ["entry", "mid"], "locations": ["Leeds", "Cambridge", "Remote (UK)"],
            "work_arrangements": ["hybrid", "remote"], "authorized_countries": ["GB"],
            "salary_min": 34000, "salary_currency": "GBP",
            "skills": ["SQL", "Python", "pandas", "Power BI", "Statistics", "Data visualisation"],
            "languages": [{"name": "English", "level": "native"}],
        },
        cv={
            "links": ["https://example.com/sam-portfolio"],
            "experience": [
                {"title": "Data Analyst", "employer": "Humongous Insurance", "location": "Leeds", "start": "2023",
                 "bullets": ["Built the Power BI claims dashboard used by 40 people every week",
                             "Automated a monthly report in Python, saving two days a month"]},
                {"title": "Graduate Analyst", "employer": "Wide World Importers", "location": "Birmingham",
                 "start": "2021", "end": "2023", "bullets": ["Wrote SQL for stock and sales reporting"]},
            ],
            "education": [{"qualification": "BSc Mathematics", "institution": "University of Leeds", "start": "2018", "end": "2021"}],
        },
        saved=("Junior Data Scientist",),
        tracked=(
            Tracked("Data Analyst", "interviewing", 8, "Take-home SQL test", 3, history=(("applied", 8), ("interviewing", 2))),
            Tracked("Data Scientist", "planned", None, "Finish the portfolio project first", 5),
            Tracked("Insight Analyst", "applied", 6, company="Northwind Traders", location="Leeds"),
        ),
    ),
    DemoPerson(
        key="engineer", name="Alex Example", headline="Software engineer",
        description="A backend engineer in London, after hybrid or remote work.",
        onboarding={
            "display_name": "Alex Example", "headline": "Software engineer", "industry": "software-engineering", "market": "uk",
            "summary": "Backend engineer who likes Python, clean APIs and boring infrastructure; looking for a senior role.",
            "years_experience": 6, "roles": ["software-engineer", "backend-engineer", "full-stack-engineer"],
            "seniority_levels": ["mid", "senior"], "locations": ["London", "Remote (UK)"],
            "work_arrangements": ["hybrid", "remote"], "authorized_countries": ["GB"],
            "salary_min": 60000, "salary_currency": "GBP",
            "skills": ["Python", "TypeScript", "SQL", "Docker", "AWS", "REST APIs", "System design"],
            "languages": [{"name": "English", "level": "native"}, {"name": "German", "level": "professional"}],
        },
        cv={
            "links": ["https://example.com/alex"],
            "experience": [
                {"title": "Software Engineer", "employer": "Litware", "location": "London", "start": "2021",
                 "bullets": ["Designed the payments API that handles 2 million requests a day",
                             "Cut deploy time from 40 minutes to 8 with a new CI pipeline"]},
                {"title": "Junior Developer", "employer": "Fabrikam", "location": "Edinburgh", "start": "2018", "end": "2021",
                 "bullets": ["Built internal tools in Python and React"]},
            ],
            "education": [{"qualification": "BSc Computer Science", "institution": "University of Edinburgh", "start": "2014", "end": "2018"}],
        },
        saved=("Full Stack Engineer",),
        tracked=(
            Tracked("Senior Backend Engineer (Python)", "offer", 18, "Reply to the offer", 4,
                    "Offer: £85,000, fully remote. Ask about the on-call rota.",
                    history=(("applied", 18), ("interviewing", 11), ("offer", 1))),
            Tracked("Software Engineer", "interviewing", 7, "System design interview", 2, history=(("applied", 7), ("interviewing", 2))),
            Tracked("Platform Engineer", "rejected", 30, company="Contoso", location="London",
                    history=(("applied", 30), ("rejected", 16))),
        ),
    ),
)}


class DemoError(ValueError):
    pass


def recent_accounts(db: Session, now: dt.datetime) -> int:
    return db.scalar(select(func.count()).select_from(User).where(
        User.email.like(f"%@{EMAIL_DOMAIN}"), User.created_at >= now - dt.timedelta(hours=1))) or 0


def _job(db: Session, user: User, title: str) -> UserJob | None:
    return db.scalar(select(UserJob).join(Job, UserJob.job_id == Job.id)
                     .where(UserJob.user_id == user.id, Job.title == title).limit(1))


def _track(db: Session, user: User, item: Tracked, now: dt.datetime) -> None:
    """An application with a believable past: made on its first status's day,
    then each later status on its own day."""
    user_job = None if item.company else _job(db, user, item.title)
    if user_job is None and not item.company:
        return  # the sample jobs changed; skip rather than invent one
    steps = list(item.history) or [(item.status, item.applied_days_ago or 0)]
    data = ApplicationCreate(user_job_id=user_job.id if user_job else None, title=item.title if item.company else "",
                             company=item.company, location=item.location, status=steps[0][0], notes=item.notes)
    application = applications.create(db, user, data, now=now - dt.timedelta(days=steps[0][1]))
    for status, days in steps[1:]:
        application.events.append(ApplicationEvent(user_id=user.id, kind="status", status=status,
                                                   at=now - dt.timedelta(days=days)))
    application.status = item.status
    application.applied_on = (now - dt.timedelta(days=item.applied_days_ago)).date() if item.applied_days_ago is not None else None
    application.next_step = item.next_step
    application.next_step_on = (now + dt.timedelta(days=item.next_in_days)).date() if item.next_in_days is not None else None
    application.updated_at = now - dt.timedelta(days=steps[-1][1])


def seed(db: Session, user: User, key: str, now: dt.datetime | None = None,
         settings: Settings | None = None) -> None:
    """Sets up a new demo account as the person `key`."""
    settings = settings or get_settings()
    now = now or dt.datetime.now(dt.UTC)
    person = PEOPLE.get(key)
    if not settings.demo_mode:
        raise DemoError("Demo mode is off.")
    if person is None:
        raise DemoError("No such demo person.")
    if not is_demo_user(user) or user.profile is not None:
        raise DemoError("Only a new demo account can be set up as a demo person.")

    payload = OnboardingWrite.model_validate(person.onboarding)
    industry = get_catalog().industries[payload.industry]
    profile = profiles.save_profile(db, user, payload)
    profiles.replace_targets(db, user, profiles.preset_targets(industry, payload.roles) + payload.custom_roles)
    profiles.finish_onboarding(profile)
    user.name = person.name
    search = SavedSearch(user_id=user.id, created_at=now, updated_at=now, next_run_at=now + EVERY, **runs.suggestion(user))
    user.searches.append(search)
    db.flush()
    run = SearchRun(user_id=user.id, search_id=search.id, trigger="onboarding", status="queued", counts={}, errors=[])
    db.add(run)
    db.commit()
    runs.run_task(db, run.id)  # the sample jobs are local: run it now, not on the worker

    # Simulated scores take no time either; real ones stay on the worker.
    task = db.scalar(select(Task).where(Task.user_id == user.id, Task.kind == "score", Task.status == "queued").limit(1))
    try:
        simulated = get_scorer(settings).provider == "simulated"
    except NotConfigured:
        simulated = False
    if task is not None and simulated:
        queue.succeed(db, task, scoring.run_task(db, task.payload["score_ids"], settings))

    for title in person.saved:
        if (user_job := _job(db, user, title)) is not None:
            user_job.state = "saved"
    for item in person.tracked:
        _track(db, user, item, now)
    cv_service.save(db, user, CvContent.model_validate({**cv_service.from_profile(user).model_dump(), **person.cv}))
    db.commit()
    cv_service.queue_pdf(db, user)
    db.commit()
    log.info("Set up a demo account as %s", key, extra={"user_id": user.id})


def expire(db: Session, now: dt.datetime | None = None, settings: Settings | None = None) -> int:
    """Deletes demo accounts older than DEMO_ACCOUNT_HOURS, files and all."""
    settings = settings or get_settings()
    now = now or dt.datetime.now(dt.UTC)
    old = db.scalars(select(User).where(User.email.like(f"%@{EMAIL_DOMAIN}"),
                                        User.created_at < now - dt.timedelta(hours=settings.demo_account_hours))
                     .limit(200)).all()
    for user in old:
        privacy.delete_account(db, user)
    if old:
        log.info("Deleted %d expired demo account(s)", len(old))
    return len(old)


def people() -> list[dict]:
    return [{"key": p.key, "name": p.name, "headline": p.headline, "description": p.description} for p in PEOPLE.values()]


__all__ = ["EMAIL_DOMAIN", "PEOPLE", "DemoError", "expire", "is_demo_user", "people", "recent_accounts", "seed"]
