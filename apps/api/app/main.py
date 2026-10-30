"""The Job Hunter API. Run with `uvicorn app.main:app` (Docker does); the web
app is its only client - see app/auth.py."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, me, presets
from app.auth import check_secret
from app.config import get_settings
from app.presets import get_catalog


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    check_secret(get_settings())
    get_catalog()  # a broken preset stops the API here, with the file named, not on first use
    yield


app = FastAPI(title="Job Hunter API", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(me.router)
app.include_router(presets.router)
