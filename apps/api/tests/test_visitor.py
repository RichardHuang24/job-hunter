"""Visitor-owned target roles and empty CVs, independent of sample personas."""
import pytest

from app.cv.schema import CvContent
from app.db.models import Cv, SavedSearch, User
from tests.conftest import auth
from tests.test_demo import demo_on, demo_user
from tests.test_search import work


@pytest.mark.parametrize("title,industry", [("Data Analyst", "data-ai"), ("Registered Nurse", "healthcare"), ("Urban Planner", "general"), ("数据分析师", "general")])
def test_role_starts_workspace_without_invented_personal_data(client, sessions, demo_on, title, industry):
    uid = demo_user(sessions)
    assert client.post("/demo/role", headers=auth(uid), json={"job_title": title}).status_code == 204
    me = client.get("/me", headers=auth(uid)).json()
    assert me["profile"]["industry"] == industry and me["profile"]["onboarded_at"]
    assert me["profile"]["skills"] == [] and me["profile"]["summary"] == ""
    assert me["targets"][0]["label"] == title
    cv = client.get("/cv", headers=auth(uid)).json()
    assert cv["content"] == CvContent().model_dump() and not cv["documents"]
    assert client.get("/applications", headers=auth(uid)).json()["total"] == 0
    with sessions() as db:
        search = db.query(SavedSearch).filter_by(user_id=uid).one()
        assert search.terms == [title] and not search.daily
    work(sessions)
    assert client.get("/searches", headers=auth(uid)).json()[0]["last_run"]["status"] == "succeeded"


def test_visitor_cv_is_isolated_and_cannot_be_reseeded(client, sessions, demo_on):
    first, second = demo_user(sessions), demo_user(sessions)
    for uid in [first, second]:
        assert client.post("/demo/role", headers=auth(uid), json={"job_title": "Data Analyst"}).status_code == 204
    content = CvContent(name="Jordan Example", email="jordan@example.com", summary="My own experience.").model_dump()
    assert client.put("/cv", headers=auth(first), json=content).status_code == 200
    assert client.get("/cv", headers=auth(second)).json()["content"] == CvContent().model_dump()
    assert client.post("/demo/role", headers=auth(first), json={"job_title": "Designer"}).status_code == 400
    assert client.get("/cv", headers=auth(first)).json()["content"] == content
    assert client.request("DELETE", "/me", headers=auth(first), json={"confirm": "DELETE"}).status_code == 204
    with sessions() as db:
        assert db.get(User, first) is None and db.get(Cv, first) is None
        assert db.get(User, second) is not None


@pytest.mark.parametrize("title", ["", " ", "x", "---", "x" * 81])
def test_invalid_roles_leave_account_unconfigured(client, sessions, demo_on, title):
    uid = demo_user(sessions)
    assert client.post("/demo/role", headers=auth(uid), json={"job_title": title}).status_code in [400, 422]
    assert client.get("/me", headers=auth(uid)).json()["profile"] is None


def test_role_entry_obeys_auth_and_demo_boundaries(client, sessions, user, demo_on, monkeypatch):
    from app.config import get_settings
    assert client.post("/demo/role", json={"job_title": "Analyst"}).status_code == 401
    assert client.post("/demo/role", headers=auth(user.id), json={"job_title": "Analyst"}).status_code == 400
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    assert client.post("/demo/role", headers=auth(user.id), json={"job_title": "Analyst"}).status_code == 404
