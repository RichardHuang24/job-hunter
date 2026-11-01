"""Privacy: a copy of everything kept about you, deleting your account with
all of it, and the facts the privacy page states."""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile

from sqlalchemy import func, select, text

from app.config import Settings, get_settings
from app.cv.build import Pdf
from app.db.models import Account, AuthSession, Base, Job, User, VerificationToken
from app.privacy import facts
from tests.conftest import auth
from tests.test_search import onboard, work

SECRET = "oauth-secret-access-token-do-not-export"


def busy_user(client, sessions, user, monkeypatch):
    """A user with a bit of everything: profile, jobs and scores, an
    application, a saved CV and a PDF, a GitHub login and a session."""
    from app.cv import service

    monkeypatch.setattr(service, "build_pdf", lambda source, settings=None: Pdf(b"%PDF-1.7 mine", 1))
    onboard(client, user)
    work(sessions)
    job = client.get("/jobs", headers=auth(user.id)).json()["items"][0]
    client.post("/applications", headers=auth(user.id), json={"user_job_id": job["id"]})
    client.put("/cv", headers=auth(user.id), json={"name": "Alex Example", "summary": "Nurse."})
    client.post("/cv/pdf", headers=auth(user.id))
    work(sessions)
    with sessions() as session:
        session.add(Account(user_id=user.id, type="oauth", provider="github", provider_account_id="12345", access_token=SECRET))
        session.add(AuthSession(user_id=user.id, expires=dt.datetime.now(dt.UTC) + dt.timedelta(days=1),
                                session_token="session-token-do-not-export"))
        session.add(VerificationToken(identifier="alex@example.com", token="t", expires=dt.datetime.now(dt.UTC)))
        session.commit()


def other_user(sessions) -> int:
    with sessions() as session:
        other = User(email="kim@example.com", name="Kim")
        session.add(other)
        session.commit()
        return other.id


def test_the_export_has_everything_and_no_secrets(client, sessions, user, monkeypatch):
    busy_user(client, sessions, user, monkeypatch)
    response = client.get("/me/export", headers=auth(user.id))
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == f'attachment; filename="job-hunter-my-data-{dt.date.today()}.zip"'
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert {"README.txt", "data.json", "applications.csv"} <= set(names)
    [pdf] = [n for n in names if n.startswith("cv/")]
    assert pdf.startswith("cv/CV - Alex Example (") and archive.read(pdf) == b"%PDF-1.7 mine"

    data = json.loads(archive.read("data.json"))
    assert data["account"]["email"] == "alex@example.com" and data["account"]["sign_in_with"] == ["github"]
    assert data["profile"]["headline"] == "Registered nurse" and data["target_roles"]
    assert data["saved_searches"] and data["search_runs"]
    assert data["jobs"] and all(j["job"]["title"] for j in data["jobs"])
    assert any(j["ai_score"] and j["ai_score"]["overall"] is not None for j in data["jobs"])
    assert data["applications"][0]["history"][0]["kind"] == "created"
    assert data["cv"]["name"] == "Alex Example" and data["documents"][0]["status"] == "done"
    assert "storage_key" not in data["documents"][0]
    everything = b"".join(archive.read(n) for n in names)
    assert SECRET.encode() not in everything and b"session-token-do-not-export" not in everything
    rows = archive.read("applications.csv").decode("utf-8-sig").strip().splitlines()
    assert rows[0].startswith("Company,Job title") and data["applications"][0]["title"] in rows[1]


def test_the_export_is_only_yours(client, sessions, user, monkeypatch):
    busy_user(client, sessions, user, monkeypatch)
    other = other_user(sessions)
    data = json.loads(zipfile.ZipFile(io.BytesIO(client.get("/me/export", headers=auth(other)).content)).read("data.json"))
    assert data["account"]["email"] == "kim@example.com"
    assert data["jobs"] == [] and data["applications"] == [] and data["cv"] is None and data["documents"] == []
    assert client.get("/me/export").status_code == 401


def test_deleting_an_account_removes_everything(client, sessions, user, monkeypatch, tmp_path):
    busy_user(client, sessions, user, monkeypatch)
    other = other_user(sessions)
    client.post("/applications", headers=auth(other), json={"title": "Kim's application"})
    assert list((tmp_path / "files").rglob("*.pdf"))

    assert client.request("DELETE", "/me", headers=auth(user.id), json={"confirm": "someone@example.com"}).status_code == 400
    assert client.request("DELETE", "/me", headers=auth(user.id), json={}).status_code == 422
    assert client.request("DELETE", "/me", headers=auth(user.id), json={"confirm": " ALEX@example.com "}).status_code == 204

    with sessions() as session:
        for table in Base.metadata.sorted_tables:
            column = table.c.get("user_id") if "user_id" in table.c else table.c.get("userId")
            if column is not None:
                left = session.scalar(select(func.count()).select_from(table).where(column == user.id))
                assert left == 0, f"{table.name} still has {left} rows"
        assert session.get(User, user.id) is None
        assert session.scalar(text("select count(*) from verification_token where identifier = 'alex@example.com'")) == 0
        assert session.scalar(select(func.count()).select_from(Job)) > 0  # shared postings stay
        assert session.get(User, other) is not None
    assert not list((tmp_path / "files").rglob("*.pdf"))  # the files went too
    assert client.get("/me", headers=auth(user.id)).status_code == 401
    assert client.get("/applications", headers=auth(other)).json()["counts"]["active"] == 1  # nobody else's


def test_the_privacy_facts(client, monkeypatch):
    response = client.get("/privacy")  # public: no sign-in
    assert response.status_code == 200
    stated = response.json()
    assert not stated["configured"] and stated["ai_provider"] == "simulated" and stated["sources"] == []  # demo isn't listed
    assert stated["storage"] == "" and not stated["billing"] and stated["cv_files_kept"] == 10

    monkeypatch.setenv("PRIVACY_CONTROLLER", "Example Careers Ltd")
    monkeypatch.setenv("PRIVACY_CONTACT", "privacy@example.com")
    get_settings.cache_clear()
    stated = client.get("/privacy").json()
    assert stated["configured"] and stated["controller"] == "Example Careers Ltd"

    s3 = facts(Settings(storage_backend="s3", s3_endpoint_url="https://acct.r2.cloudflarestorage.com", job_sources="himalayas,jobicy",
                        anthropic_api_key="sk-test"))
    assert s3["storage"] == "acct.r2.cloudflarestorage.com" and s3["ai_provider"] == "anthropic"
    assert [s["label"] for s in s3["sources"]] == ["Himalayas", "Jobicy"]
    assert facts(Settings(storage_backend="s3", s3_endpoint_url="http://storage:7070"))["storage"] == ""  # the stack's own
    assert facts(Settings(storage_backend="s3", s3_endpoint_url=""))["storage"] == "Amazon S3"
