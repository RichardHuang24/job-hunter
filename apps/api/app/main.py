"""The Job Hunter API. Run with `uvicorn app.main:app` (Docker does); the web
app is its only client - see app/auth.py."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import admin, applications, billing, cv, demo, health, jobs, me, presets, privacy, searches, sources
from app.auth import check_secret
from app.config import get_settings
from app.observability import RequestLog, init_sentry, setup_logging
from app.presets import get_catalog

setup_logging()
init_sentry("api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    check_secret(get_settings())
    get_catalog()  # a broken preset stops the API here, with the file named, not on first use
    yield


app = FastAPI(title="Job Hunter API", version=get_settings().app_version, lifespan=lifespan)
app.add_middleware(RequestLog)
app.include_router(health.router)
app.include_router(me.router)
app.include_router(presets.router)
app.include_router(sources.router)
app.include_router(searches.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(cv.router)
app.include_router(billing.router)
app.include_router(privacy.router)
app.include_router(admin.router)
app.include_router(demo.router)
