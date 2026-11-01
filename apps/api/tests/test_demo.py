"""Demo mode: fictional people to try Job Hunter as, each a fresh account
that's set up in one go and deleted after a day."""

from __future__ import annotations

import datetime as dt

import pytest

from app import demo
from app.config import get_settings
from app.cv.build import Pdf
from app.db.models import Application, Cv, Document, User, UserJob
from tests.conftest import auth
from tests.test_search import work

NOW = dt.datetime.now(dt.UTC)


@pytest.fixture()
def demo_on(monkeypatch):
    from app.cv import service

    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(service, "build_pdf", lambda source, settings=None: Pdf(b"%PDF-1.7 demo", 1))


def demo_user(sessions, created: dt.datetime | None = None, email: str | None = None) -> int:
    with sessions() as session:
        person = User(email=email or f"demo-{len(session.query(User).all())}@demo.invalid")
        if created:
            person.created_at = created
        session.add(person)
        session.commit()
        return person.id


def test_the_demo_is_off_unless_asked(client, sessions):
    assert client.get("/demo").json() == {"enabled": False, "account_hours": 24, "people": []}
    uid = demo_user(sessions)
    assert client.post("/demo/seed", headers=auth(uid), json={"person": "nurse"}).status_code == 404


@pytest.mark.parametrize("key", list(demo.PEOPLE))
def test_each_person_arrives_with_everything_set_up(client, sessions, demo_on, key):
    listed = client.get("/demo").json()
    assert listed["enabled"] and [p["key"] for p in listed["people"]] == list(demo.PEOPLE)
    uid = demo_user(sessions)
    assert client.post("/demo/seed", headers=auth(uid), json={"person": key}).status_code == 204
    person = demo.PEOPLE[key]

    me = client.get("/me", headers=auth(uid)).json()
    assert me["profile"]["onboarded_at"] and me["name"] == person.name and me["targets"]
    jobs = client.get("/jobs", headers=auth(uid), params={"view": "matches"}).json()
    assert jobs["counts"]["matches"] >= 2, jobs["counts"]
    assert all(i["score"] and i["score"]["status"] == "done" for i in jobs["items"])  # scored already
    assert jobs["counts"]["saved"] == len(person.saved)

    apps = client.get("/applications", headers=auth(uid), params={"view": "all"}).json()
    assert apps["total"] == len(person.tracked)  # every one found its job
    by_title = {a["title"]: a for a in apps["items"]}
    for item in person.tracked:
        made = by_title[item.title]
        assert made["status"] == item.status and made["next_step"] == item.next_step
        detail = client.get(f"/applications/{made['id']}", headers=auth(uid)).json()
        assert [e["status"] for e in detail["events"]] == [s for s, _ in item.history] or not item.history
        assert detail["events"] == sorted(detail["events"], key=lambda e: e["at"])

    cv = client.get("/cv", headers=auth(uid)).json()
    assert cv["saved"] and cv["content"]["experience"] and cv["content"]["name"] == person.name
    assert cv["documents"][0]["status"] == "queued"
    work(sessions)
    assert client.get("/cv", headers=auth(uid)).json()["documents"][0]["status"] == "done"


def test_only_new_demo_accounts_can_be_set_up(client, sessions, user, demo_on):
    assert client.post("/demo/seed", headers=auth(user.id), json={"person": "nurse"}).status_code == 400  # not a demo address
    uid = demo_user(sessions)
    assert client.post("/demo/seed", headers=auth(uid), json={"person": "astronaut"}).status_code == 400
    assert client.post("/demo/seed", headers=auth(uid), json={"person": "nurse"}).status_code == 204
    assert client.post("/demo/seed", headers=auth(uid), json={"person": "nurse"}).status_code == 400  # once only
    assert client.post("/demo/seed", json={"person": "nurse"}).status_code == 401


def test_too_many_new_demo_accounts_wait(client, sessions, demo_on, monkeypatch):
    monkeypatch.setenv("DEMO_ACCOUNTS_PER_HOUR", "2")
    get_settings.cache_clear()
    ids = [demo_user(sessions) for _ in range(3)]
    assert client.post("/demo/seed", headers=auth(ids[0]), json={"person": "analyst"}).status_code == 429


def test_demo_accounts_expire_after_a_day(client, sessions, user, demo_on, tmp_path):
    old = demo_user(sessions, created=NOW - dt.timedelta(hours=25))
    client.post("/demo/seed", headers=auth(old), json={"person": "engineer"})
    work(sessions)
    fresh = demo_user(sessions, created=NOW - dt.timedelta(hours=2))
    assert list((tmp_path / "files").rglob("*.pdf"))
    with sessions() as session:
        assert demo.expire(session, NOW) == 1
    with sessions() as session:
        assert session.get(User, old) is None and session.get(User, fresh) is not None and session.get(User, user.id)
        assert not session.query(UserJob).filter_by(user_id=old).count()
        assert not session.query(Application).filter_by(user_id=old).count()
        assert session.get(Cv, old) is None and not session.query(Document).filter_by(user_id=old).count()
    assert not list((tmp_path / "files").rglob("*.pdf"))  # files too
    with sessions() as session:
        assert demo.expire(session, NOW) == 0
