"""Test fixtures: a throwaway database per test - SQLite by default, or the
Postgres at TEST_DATABASE_URL (CI runs both) - and signed tokens like the
ones the web app sends."""

from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import Base, User
from app.db.session import get_db, make_engine
from sqlalchemy.orm import sessionmaker

SECRET = "test-secret-" + "x" * 40


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv("BACKEND_JWT_SECRET", SECRET)
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def sessions(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(sessions):
    from app.main import app

    def override():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user(sessions) -> User:
    with sessions() as session:
        person = User(email="alex@example.com", name="Alex Example")
        session.add(person)
        session.commit()
        return person


def token(user_id: int | str, *, secret: str = SECRET, minutes: int = 1, **overrides) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {"sub": str(user_id), "iss": "job-hunter-web", "aud": "job-hunter-api", "iat": now,
              "exp": now + dt.timedelta(minutes=minutes), **overrides}
    return jwt.encode(claims, secret, algorithm="HS256")


def auth(user_id: int | str, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(user_id, **kwargs)}"}
