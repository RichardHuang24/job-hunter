"""Saved searches, runs on the worker, the shared job store and each user's
jobs - end to end through the API, with the built-in sample jobs."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from app.db.models import Job, SavedSearch, SearchRun, Task, User, UserJob
from app.search.queries import build_queries
from app.search.schedule import schedule_due
from app.sources.base import Posting, Query, Source
from app.worker import run_one
from tests.conftest import auth

NURSE = {
    "display_name": "Alex", "headline": "Registered nurse", "industry": "healthcare", "market": "uk",
    "roles": ["registered-nurse"], "custom_roles": [{"label": "Research nurse", "titles": ["research nurse"]}],
    "seniority_levels": ["mid", "senior"], "locations": ["Manchester"], "work_arrangements": ["onsite", "hybrid"],
    "authorized_countries": ["GB"], "salary_min": 32000, "salary_currency": "GBP",
}


def onboard(client, user, **changes):
    response = client.post("/me/onboarding", headers=auth(user.id), json={**NURSE, **changes})
    assert response.status_code == 200, response.text


def work(sessions):
    """Runs every queued task, as the worker would."""
    while run_one(sessions, "test-worker", 600):
        pass


def jobs(client, user, view="matches", **params):
    return client.get("/jobs", headers=auth(user.id), params={"view": view, **params}).json()


def titles(listing):
    return {item["job"]["title"] for item in listing["items"]}


def test_queries_cover_every_term_in_every_place():
    queries, dropped = build_queries(["staff nurse", "Staff nurse ", "research nurse"], ["Manchester", "Remote (UK)"], ["GB"], False)
    assert [(q.term, q.location, q.remote) for q in queries] == [
        ("staff nurse", "Manchester", False), ("staff nurse", "", True),
        ("Staff nurse", "Manchester", False), ("Staff nurse", "", True),
        ("research nurse", "Manchester", False), ("research nurse", "", True),
    ] and not dropped
    queries, _ = build_queries(["chef"], [], [], True)
    assert [(q.location, q.remote) for q in queries] == [("", False), ("", True)]
    _, dropped = build_queries([f"term {i}" for i in range(10)], [f"Town {i}" for i in range(5)], [], False)
    assert dropped


def test_onboarding_makes_a_search_and_the_worker_runs_it(client, sessions, user):
    onboard(client, user)
    [search] = client.get("/searches", headers=auth(user.id)).json()
    assert search["name"] == "From your profile" and search["countries"] == ["GB"] and search["daily"]
    assert {"registered nurse", "staff nurse", "Research nurse"} <= set(search["terms"])
    assert search["last_run"]["status"] == "queued" and search["last_run"]["trigger"] == "onboarding"

    work(sessions)
    run = client.get(f"/runs/{search['last_run']['id']}", headers=auth(user.id)).json()
    assert run["status"] == "succeeded" and run["errors"] == []
    assert run["counts"]["new"] == run["counts"]["found"] > 0 and run["counts"]["by_source"]["demo"] > 0

    matches = jobs(client, user)
    assert titles(matches) >= {"Staff Nurse - Acute Medicine", "Senior Staff Nurse - Band 6",
                               "Registered Nurse - Day Surgery", "Research Nurse"}
    research = next(i for i in matches["items"] if i["job"]["title"] == "Research Nurse")
    assert research["role"] == "Research nurse" and research["job"]["demo"]
    assert titles(jobs(client, user, "flagged")) == {"Registered Nurse - Nights"}
    filtered = jobs(client, user, "filtered")
    lead = next(i for i in filtered["items"] if i["job"]["title"] == "Lead Staff Nurse - Band 7")
    assert {c["key"]: c["status"] for c in lead["checks"]}["level"] == "fail"
    assert matches["counts"] == {"matches": len(matches["items"]), "flagged": 1, "filtered": len(filtered["items"]),
                                 "saved": 0, "hidden": 0}


def test_saving_hiding_and_running_again(client, sessions, user):
    onboard(client, user)
    work(sessions)
    matches = jobs(client, user)["items"]
    first, second = matches[0]["id"], matches[1]["id"]
    assert client.patch(f"/jobs/{first}", headers=auth(user.id), json={"state": "saved"}).json()["state"] == "saved"
    client.patch(f"/jobs/{second}", headers=auth(user.id), json={"state": "hidden"})
    assert client.patch(f"/jobs/{second}", headers=auth(user.id), json={"state": "binned"}).status_code == 422

    [search] = client.get("/searches", headers=auth(user.id)).json()
    run = client.post(f"/searches/{search['id']}/run", headers=auth(user.id))
    assert run.status_code == 202
    assert client.post(f"/searches/{search['id']}/run", headers=auth(user.id)).status_code == 409  # one at a time
    work(sessions)
    again = client.get(f"/runs/{run.json()['id']}", headers=auth(user.id)).json()
    assert again["status"] == "succeeded" and again["counts"]["new"] == 0  # nothing new the second time
    assert [i["id"] for i in jobs(client, user, "saved")["items"]] == [first]
    assert [i["id"] for i in jobs(client, user, "hidden")["items"]] == [second]
    assert second not in {i["id"] for i in jobs(client, user)["items"]}
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == again["counts"]["found"]  # stored once


def test_a_job_in_detail(client, sessions, user):
    onboard(client, user)
    work(sessions)
    item = jobs(client, user, q="acute")["items"][0]
    detail = client.get(f"/jobs/{item['id']}", headers=auth(user.id)).json()
    assert detail["job"]["title"] == "Staff Nurse - Acute Medicine"
    assert "fictional" in detail["job"]["description"] and detail["level"] == {"key": "mid", "label": "Mid level"}
    assert jobs(client, user, q="no such job anywhere")["total"] == 0


def test_changing_the_profile_rejudges_jobs(client, sessions, user):
    onboard(client, user)
    work(sessions)
    assert "Lead Staff Nurse - Band 7" in titles(jobs(client, user, "filtered"))
    profile = client.get("/me", headers=auth(user.id)).json()["profile"]
    body = {k: v for k, v in profile.items() if k not in ("onboarded_at", "updated_at")}
    client.put("/me/profile", headers=auth(user.id), json={**body, "seniority_levels": []})
    assert "Lead Staff Nurse - Band 7" in titles(jobs(client, user))
    client.put("/me/targets", headers=auth(user.id), json=[{"label": "Research nurse", "titles": ["research nurse"]}])
    assert titles(jobs(client, user)) == {"Research Nurse"}


class Twin(Source):
    """Lists one sample job again, as a second board would."""

    key, label, description, commercial = "twin", "Twin board", "Test source", True

    def search(self, query: Query) -> list[Posting]:
        return [Posting(source_id="t-1", url="https://example.org/t-1", title="Staff Nurse - Acute Medicine",
                        company="Contoso Health", location="Manchester", country="GB", arrangement="onsite")]


class Broken(Source):
    key, label, description, commercial = "broken", "Broken board", "Always fails", True

    def search(self, query: Query) -> list[Posting]:
        raise TimeoutError("board didn't answer")


def test_duplicates_across_sources_and_a_failing_source(client, sessions, user, monkeypatch):
    from app.search import runs
    from app.sources.demo import DemoSource

    monkeypatch.setattr(runs, "enabled_sources", lambda: [DemoSource(), Twin(), Broken()])
    onboard(client, user)
    work(sessions)
    [search] = client.get("/searches", headers=auth(user.id)).json()
    run = search["last_run"]
    assert run["status"] == "succeeded"
    assert run["errors"] == [{"source": "broken", "message": "TimeoutError: board didn't answer"}]
    assert run["counts"]["by_source"]["twin"] == 1
    acute = [i for i in jobs(client, user)["items"] if i["job"]["title"] == "Staff Nurse - Acute Medicine"]
    assert len(acute) == 1  # listed twice, shown once


def test_a_run_that_crashes_is_marked_failed(client, sessions, user, monkeypatch):
    from app.search import runs

    def explode(*args, **kwargs):
        raise RuntimeError("database fell over")

    monkeypatch.setattr(runs, "run_search", explode)
    onboard(client, user)
    work(sessions)
    run = client.get("/searches", headers=auth(user.id)).json()[0]["last_run"]
    assert run["status"] == "failed" and "database fell over" in run["errors"][0]["message"]
    with sessions() as session:
        assert session.scalar(select(Task.status)) == "failed"


def test_daily_searches_are_queued_when_due(client, sessions, user):
    onboard(client, user)
    work(sessions)
    now = dt.datetime.now(dt.UTC)
    with sessions() as session:
        assert schedule_due(session, now) == 0  # not due for a day
        assert schedule_due(session, now + dt.timedelta(days=1, minutes=1)) == 1
        assert schedule_due(session, now + dt.timedelta(days=1, minutes=2)) == 0  # next one is tomorrow
        search = session.scalar(select(SavedSearch))
        assert search.next_run_at.replace(tzinfo=dt.UTC) > now + dt.timedelta(days=2)
        assert session.scalar(select(SearchRun).where(SearchRun.trigger == "schedule")).status == "queued"


def test_managing_saved_searches(client, user):
    headers = auth(user.id)
    suggestion = client.get("/searches/suggestion", headers=headers).json()
    assert suggestion["terms"] == [] and suggestion["name"] == "From your profile"
    created = client.post("/searches", headers=headers, json={
        "name": "Chef jobs", "terms": ["sous chef", " Sous chef"], "locations": ["Bristol"], "countries": ["gb"],
        "daily": False})
    assert created.status_code == 201, created.text
    search = created.json()
    assert search["terms"] == ["sous chef"] and search["countries"] == ["GB"] and search["next_run_at"] is None
    updated = client.put(f"/searches/{search['id']}", headers=headers, json={**{k: search[k] for k in (
        "name", "terms", "locations", "countries", "include_remote", "sources")}, "daily": True}).json()
    assert updated["next_run_at"] is not None
    for bad in ({"name": "x", "terms": []}, {"name": "x", "terms": ["a"], "countries": ["XX"]},
                {"name": "x", "terms": ["a"], "sources": ["nowhere"]}, {"name": "", "terms": ["a"]}):
        assert client.post("/searches", headers=headers, json=bad).status_code == 422, bad
    for i in range(4):
        client.post("/searches", headers=headers, json={"name": f"S{i}", "terms": ["chef"]})
    assert client.post("/searches", headers=headers, json={"name": "One too many", "terms": ["chef"]}).status_code == 409
    assert client.delete(f"/searches/{search['id']}", headers=headers).status_code == 204
    assert len(client.get("/searches", headers=headers).json()) == 4
    assert client.get("/sources", headers=headers).json()[0]["key"] == "demo"


def test_nobody_sees_or_touches_another_users_searches_or_jobs(client, sessions, user):
    onboard(client, user)
    work(sessions)
    with sessions() as session:
        other = User(email="sam@example.com")
        session.add(other)
        session.commit()
    mine = jobs(client, user)["items"][0]["id"]
    [search] = client.get("/searches", headers=auth(user.id)).json()
    them = auth(other.id)
    assert jobs(client, other)["total"] == 0 and client.get("/searches", headers=them).json() == []
    assert client.get(f"/jobs/{mine}", headers=them).status_code == 404
    assert client.patch(f"/jobs/{mine}", headers=them, json={"state": "hidden"}).status_code == 404
    assert client.post(f"/searches/{search['id']}/run", headers=them).status_code == 404
    assert client.delete(f"/searches/{search['id']}", headers=them).status_code == 404
    assert client.get(f"/runs/{search['last_run']['id']}", headers=them).status_code == 404
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(UserJob).where(UserJob.user_id == other.id)) == 0
