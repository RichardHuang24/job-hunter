"""Scoring end to end: after searches, on request, within the allowance -
through the API and the worker."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.db.models import AiUsage, JobScore, User
from app.scoring import service
from tests.conftest import auth
from tests.test_scoring_providers import Client, response
from tests.test_search import NURSE, jobs, onboard, titles, work


def test_new_matches_are_scored_after_a_search(client, sessions, user):
    onboard(client, user)
    work(sessions)
    matches = jobs(client, user)["items"]
    assert matches and all(i["score"]["status"] == "done" and i["score"]["simulated"] for i in matches)
    assert all(i["score"]["status"] == "done" for i in jobs(client, user, "flagged")["items"])
    assert all(i["score"] is None for i in jobs(client, user, "filtered")["items"])  # not scored unless asked
    detail = client.get(f"/jobs/{matches[0]['id']}", headers=auth(user.id)).json()["score"]
    assert {d["key"] for d in detail["dimensions"]} == {"skills", "experience", "culture", "career"}
    assert sum(d["weight"] for d in detail["dimensions"]) == 100 and detail["advice"]
    assert detail["provider"] == "simulated" and detail["cost_usd"] == 0 and not detail["stale"]
    ai = client.get("/me/ai", headers=auth(user.id)).json()
    assert ai["provider"] == "simulated" and ai["scores_used"] == len(matches) + 1 and ai["queued"] == 0


def test_best_fit_first(client, sessions, user):
    onboard(client, user, skills=["Acute medicine", "Clinical trial", "Surgery"])
    work(sessions)
    ranked = jobs(client, user, sort="fit")["items"]
    scores = [i["score"]["overall"] for i in ranked]
    assert scores == sorted(scores, reverse=True) and scores[0] > scores[-1]


def test_scoring_a_job_on_request(client, sessions, user):
    onboard(client, user)
    work(sessions)
    lead = next(i for i in jobs(client, user, "filtered")["items"] if i["job"]["title"] == "Lead Staff Nurse - Band 7")
    queued = client.post(f"/jobs/{lead['id']}/score", headers=auth(user.id))
    assert queued.status_code == 202 and queued.json()["status"] == "queued"
    assert client.post(f"/jobs/{lead['id']}/score", headers=auth(user.id)).status_code == 409
    work(sessions)
    score = client.get(f"/jobs/{lead['id']}", headers=auth(user.id)).json()["score"]
    assert score["status"] == "done" and score["overall"] is not None
    assert "isn't a level you want" in next(d["reason"] for d in score["dimensions"] if d["key"] == "experience")


def test_a_changed_profile_makes_scores_stale(client, sessions, user):
    onboard(client, user)
    work(sessions)
    profile = client.get("/me", headers=auth(user.id)).json()["profile"]
    body = {k: v for k, v in profile.items() if k not in ("onboarded_at", "updated_at")}
    client.put("/me/profile", headers=auth(user.id), json={**body, "skills": ["Wound care", "Triage"]})
    assert all(i["score"]["stale"] for i in jobs(client, user)["items"])
    first = jobs(client, user)["items"][0]["id"]
    client.post(f"/jobs/{first}/score", headers=auth(user.id))
    work(sessions)
    assert not client.get(f"/jobs/{first}", headers=auth(user.id)).json()["score"]["stale"]


def test_the_monthly_allowance(client, sessions, user, monkeypatch):
    monkeypatch.setenv("AI_SCORES_PER_MONTH", "2")
    from app.config import get_settings
    get_settings.cache_clear()
    onboard(client, user)
    work(sessions)
    scored = [i for v in ("matches", "flagged") for i in jobs(client, user, v)["items"] if i["score"]]
    assert len(scored) == 2  # the rest wait for next month
    unscored = next(i for i in jobs(client, user)["items"] if i["score"] is None)
    refused = client.post(f"/jobs/{unscored['id']}/score", headers=auth(user.id))
    assert refused.status_code == 429
    assert client.get("/me/ai", headers=auth(user.id)).json()["scores_used"] == 2


def test_the_monthly_budget(client, sessions, user):
    onboard(client, user, roles=["registered-nurse"])
    with sessions() as session:  # spend the budget before the worker gets to the queue
        session.add(AiUsage(user_id=user.id, provider="anthropic", model="claude-opus-5-5", cost_usd=5.0,
                            created_at=dt.datetime.now(dt.UTC)))
        session.commit()
    work(sessions)
    [search] = client.get("/searches", headers=auth(user.id)).json()
    assert search["last_run"]["counts"]["scoring"] == 0  # nothing queued over budget
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(JobScore)) == 0


def test_claude_through_the_worker(client, sessions, user, monkeypatch):
    """The real scorer's path end to end, with a stand-in for the API."""
    from app.scoring import providers
    from app.scoring.providers import AnthropicScorer

    stub = Client(response())
    monkeypatch.setattr(service, "get_scorer", lambda settings=None: AnthropicScorer(stub, "claude-opus-5-5", "medium"))
    onboard(client, user)
    work(sessions)
    assert stub.calls and all(where == "beta" for where, _ in stub.calls)
    system = stub.calls[0][1]["system"][0]["text"]
    assert "<candidate>" in system and "Registered nurse" in system and system == stub.calls[-1][1]["system"][0]["text"]
    item = jobs(client, user)["items"][0]
    detail = client.get(f"/jobs/{item['id']}", headers=auth(user.id)).json()["score"]
    assert detail["provider"] == "anthropic" and not detail["simulated"] and detail["cost_usd"] > 0
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(AiUsage).where(AiUsage.provider == "anthropic")) == len(stub.calls)
    assert client.get("/me/ai", headers=auth(user.id)).json()["cost_usd"] > 0
    assert providers.describe()["provider"] == "simulated"  # the deployment itself still has no key


def test_a_rejected_key_stops_the_batch(client, sessions, user, monkeypatch):
    from app.scoring.providers import AnthropicScorer
    from tests.test_scoring_providers import _status
    import anthropic

    stub = Client(_status(anthropic.AuthenticationError, 401))
    monkeypatch.setattr(service, "get_scorer", lambda settings=None: AnthropicScorer(stub, "claude-opus-5-5", "medium"))
    onboard(client, user)
    work(sessions)
    assert len(stub.calls) == 1  # one try, not one per job
    failed = [i for i in jobs(client, user)["items"]]
    detail = client.get(f"/jobs/{failed[0]['id']}", headers=auth(user.id)).json()["score"]
    assert detail["status"] == "failed" and detail["error_code"] == "auth" and "ANTHROPIC_API_KEY" in detail["error"]
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(AiUsage)) == 0


def test_nobody_scores_or_sees_another_users_scores(client, sessions, user):
    onboard(client, user)
    work(sessions)
    with sessions() as session:
        other = User(email="sam@example.com")
        session.add(other)
        session.commit()
    mine = jobs(client, user)["items"][0]["id"]
    assert client.post(f"/jobs/{mine}/score", headers=auth(other.id)).status_code == 404
    ai = client.get("/me/ai", headers=auth(other.id)).json()
    assert ai["scores_used"] == 0 and ai["cost_usd"] == 0


def test_auto_scoring_can_be_turned_off(client, sessions, user, monkeypatch):
    monkeypatch.setenv("AI_AUTO_SCORE", "false")
    from app.config import get_settings
    get_settings.cache_clear()
    onboard(client, user)
    work(sessions)
    assert all(i["score"] is None for i in jobs(client, user)["items"])
    assert titles(jobs(client, user))  # the search itself still ran
    assert NURSE  # the shared profile used above
