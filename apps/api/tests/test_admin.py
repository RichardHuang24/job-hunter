"""The admin page's numbers, and who can see them."""

from __future__ import annotations

import datetime as dt

import pytest

from app.admin import overview
from app.config import get_settings
from app.db.models import AiUsage, Document, SavedSearch, SearchRun, Task, User
from tests.conftest import auth
from tests.test_search import onboard, work

NOW = dt.datetime.now(dt.UTC)


@pytest.fixture()
def admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "ops@example.com, ALEX@example.com")
    get_settings.cache_clear()


def test_only_admins_get_in(client, user, monkeypatch):
    assert client.get("/admin/overview").status_code == 401
    assert client.get("/admin/overview", headers=auth(user.id)).status_code == 403
    assert client.get("/me", headers=auth(user.id)).json()["is_admin"] is False
    monkeypatch.setenv("ADMIN_EMAILS", "ops@example.com, ALEX@example.com")  # any case, spaces ignored
    get_settings.cache_clear()
    assert client.get("/admin/overview", headers=auth(user.id)).status_code == 200
    assert client.get("/me", headers=auth(user.id)).json()["is_admin"] is True


def _user(session, email: str) -> int:
    person = User(email=email)
    session.add(person)
    session.flush()
    return person.id


def test_ai_costs_per_person(sessions, user):
    with sessions() as session:
        kim = _user(session, "kim@example.com")
        last_month = NOW.replace(day=1) - dt.timedelta(days=2)
        for who, cost, model, at in ((user.id, 0.002, "claude-haiku-5-5", NOW), (user.id, 0.003, "claude-haiku-5-5", NOW),
                                     (kim, 0.04, "claude-opus-5-5", NOW), (kim, 9.0, "claude-opus-5-5", last_month)):
            session.add(AiUsage(user_id=who, provider="anthropic", model=model, input_tokens=1000, output_tokens=500,
                                cost_usd=cost, created_at=at))
        session.commit()
        ai = overview(session, NOW)["ai"]
    assert ai["month"] == NOW.strftime("%Y-%m") and ai["scores"] == 3 and ai["cost_usd"] == pytest.approx(0.045)
    assert [(u["email"], u["scores"], u["cost_usd"]) for u in ai["by_user"]] == [
        ("kim@example.com", 1, 0.04), ("alex@example.com", 2, 0.005)]  # last month's $9 isn't counted
    assert ai["by_user"][0]["budget_used"] == pytest.approx(0.04 / 5.0, abs=1e-3) and ai["by_user"][1]["input_tokens"] == 2000
    assert [m["model"] for m in ai["by_model"]] == ["claude-opus-5-5", "claude-haiku-5-5"]


def test_source_error_rates(sessions, user):
    with sessions() as session:
        search = SavedSearch(user_id=user.id, name="s", terms=["x"])
        session.add(search)
        session.flush()

        def run(sources: dict, errors: list, finished: dt.datetime) -> None:
            session.add(SearchRun(user_id=user.id, search_id=search.id, status="succeeded", counts={"sources": sources},
                                  errors=errors, finished_at=finished))
        ok = {"queries": 2, "postings": 5, "error": ""}
        run({"demo": ok, "himalayas": ok}, [], NOW - dt.timedelta(hours=3))
        run({"demo": ok, "himalayas": {"queries": 1, "postings": 0, "error": "SourceError: himalayas.app answered 503"}},
            [{"source": "himalayas", "message": "SourceError: himalayas.app answered 503"}], NOW - dt.timedelta(hours=1))
        run({"himalayas": {"queries": 1, "postings": 0, "error": "old failure"}}, [], NOW - dt.timedelta(days=9))  # too old
        session.add(Task(kind="recheck", status="succeeded", finished_at=NOW, result={"himalayas": {"open": 4, "closed": 1}}))
        session.commit()
        sources = {s["key"]: s for s in overview(session, NOW)["sources"]}
    demo, himalayas = sources["demo"], sources["himalayas"]
    assert (demo["runs"], demo["failed"], demo["error_rate"], demo["postings"], demo["enabled"]) == (2, 0, 0.0, 10, True)
    assert (himalayas["runs"], himalayas["failed"], himalayas["error_rate"]) == (2, 1, 0.5)
    assert himalayas["last_error"] == "SourceError: himalayas.app answered 503" and not himalayas["enabled"]
    assert himalayas["last_recheck"] == {"open": 4, "closed": 1}


def test_the_queue(sessions, user):
    with sessions() as session:
        session.add_all([
            Task(kind="score", status="queued", run_after=NOW - dt.timedelta(minutes=5)),
            Task(kind="score", status="queued", run_after=NOW + dt.timedelta(minutes=5)),  # not due yet
            Task(kind="search", status="running", locked_at=NOW - dt.timedelta(hours=2)),  # stuck past its lease
            Task(kind="search", status="succeeded", finished_at=NOW - dt.timedelta(hours=1)),
            Task(kind="cv_pdf", status="failed", finished_at=NOW - dt.timedelta(minutes=10), error="BuildError: boom",
                 user_id=user.id, attempts=1),
            Task(kind="cv_pdf", status="failed", finished_at=NOW - dt.timedelta(days=3), error="old"),
        ])
        session.add(Document(user_id=user.id, status="done", requested_at=NOW))
        session.add(Document(user_id=user.id, status="failed", requested_at=NOW))
        session.commit()
        data = overview(session, NOW)
    queue = data["queue"]
    kinds = {k["kind"]: k for k in queue["by_kind"]}
    assert kinds["score"]["queued"] == 2 and kinds["search"]["running"] == 1 and kinds["search"]["succeeded_24h"] == 1
    assert kinds["cv_pdf"]["failed_24h"] == 1  # the old failure is outside the 24 hours
    assert 290 <= queue["waiting_seconds"] <= 310 and queue["stuck"] == 1
    assert [f["error"] for f in queue["recent_failures"]] == ["BuildError: boom", "old"]
    assert data["cv_pdfs"] == {"done_7_days": 1, "failed_7_days": 1, "queued": 0}


def test_the_overview_through_the_api(client, sessions, user, admin):
    onboard(client, user)
    work(sessions)
    data = client.get("/admin/overview", headers=auth(user.id)).json()
    assert data["people"]["total"] == 1 and data["people"]["set_up"] == 1 and data["people"]["new_7_days"] == 1
    demo = next(s for s in data["sources"] if s["key"] == "demo")
    assert demo["runs"] == 1 and demo["failed"] == 0 and demo["postings"] > 0
    [scoring] = data["ai"]["by_user"]  # the simulated scorer is counted, at no cost
    assert scoring["email"] == "alex@example.com" and scoring["scores"] > 0 and scoring["cost_usd"] == 0
    assert any(k["kind"] == "search" and k["succeeded_24h"] == 1 for k in data["queue"]["by_kind"])
