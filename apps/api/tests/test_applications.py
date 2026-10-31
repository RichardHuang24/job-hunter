"""Applications: tracked from a job or by hand, their history, the lists, the
CSV export, and nobody else seeing them."""

from __future__ import annotations

import csv
import datetime as dt
import io

import pytest

from app.applications import safe_cell
from app.db.models import Application, ApplicationEvent, Job, User
from tests.conftest import auth
from tests.test_search import jobs, onboard, work

TODAY = dt.datetime.now(dt.UTC).date().isoformat()


def first_match(client, sessions, user, title="Staff Nurse - Acute Medicine"):
    onboard(client, user)
    work(sessions)
    return next(i for i in jobs(client, user)["items"] if i["job"]["title"] == title)


def apps(client, user, **params):
    return client.get("/applications", headers=auth(user.id), params=params).json()


def test_tracking_a_job(client, sessions, user):
    item = first_match(client, sessions, user)
    assert item["application"] is None
    made = client.post("/applications", headers=auth(user.id), json={"user_job_id": item["id"]})
    assert made.status_code == 201, made.text
    app = made.json()
    assert (app["title"], app["company"], app["status"], app["applied_on"]) == (
        "Staff Nurse - Acute Medicine", "Contoso Health", "applied", TODAY)
    assert app["url"] == item["job"]["url"] and app["user_job_id"] == item["id"] and not app["job_closed"]
    assert client.post("/applications", headers=auth(user.id), json={"user_job_id": item["id"]}).status_code == 409

    shown = next(i for i in jobs(client, user)["items"] if i["id"] == item["id"])
    assert shown["application"] == {"id": app["id"], "status": "applied"}
    assert client.get(f"/jobs/{item['id']}", headers=auth(user.id)).json()["application"]["status"] == "applied"


def test_adding_one_by_hand(client, user):
    assert client.post("/applications", headers=auth(user.id), json={}).status_code == 422  # needs a title or a job
    assert client.post("/applications", headers=auth(user.id), json={"title": "x", "url": "javascript:alert(1)"}).status_code == 422
    assert client.post("/applications", headers=auth(user.id), json={"title": "x", "status": "hired"}).status_code == 422
    made = client.post("/applications", headers=auth(user.id), json={
        "title": "Practice Nurse", "company": "Riverside Surgery", "status": "planned", "url": "https://example.com/job"})
    assert made.status_code == 201
    app = made.json()
    assert app["status"] == "planned" and app["applied_on"] is None and app["user_job_id"] is None
    assert client.post("/applications", headers=auth(user.id), json={"user_job_id": "nope"}).status_code == 404


def test_moving_through_statuses_keeps_a_history(client, user):
    app_id = client.post("/applications", headers=auth(user.id), json={"title": "Ward Sister", "status": "planned"}).json()["id"]
    patched = client.patch(f"/applications/{app_id}", headers=auth(user.id), json={"status": "applied"}).json()
    assert patched["applied_on"] == TODAY  # sent today, unless you say otherwise
    patched = client.patch(f"/applications/{app_id}", headers=auth(user.id), json={
        "status": "interviewing", "next_step": "Panel interview", "next_step_on": "2026-11-12", "notes": "Bring registration"}).json()
    assert (patched["next_step"], patched["next_step_on"], patched["notes"]) == ("Panel interview", "2026-11-12", "Bring registration")
    assert [(e["kind"], e["status"]) for e in patched["events"]] == [
        ("created", "planned"), ("status", "applied"), ("status", "interviewing")]
    same = client.patch(f"/applications/{app_id}", headers=auth(user.id), json={"notes": "Bring ID too", "status": "interviewing"}).json()
    assert len(same["events"]) == 3  # no new event without a new status
    cleared = client.patch(f"/applications/{app_id}", headers=auth(user.id), json={"next_step_on": None}).json()
    assert cleared["next_step_on"] is None and cleared["next_step"] == "Panel interview"
    assert client.patch(f"/applications/{app_id}", headers=auth(user.id), json={"title": None}).status_code == 422
    assert client.patch(f"/applications/{app_id}", headers=auth(user.id), json={"applied_on": "2026-10-01", "status": "offer"}).json()["applied_on"] == "2026-10-01"


def test_lists_counts_and_order(client, user):
    def add(title, status, next_on=None):
        app_id = client.post("/applications", headers=auth(user.id), json={"title": title, "status": status}).json()["id"]
        if next_on:
            client.patch(f"/applications/{app_id}", headers=auth(user.id), json={"next_step": "Call", "next_step_on": next_on})
    add("A", "applied", "2026-11-20")
    add("B", "interviewing", "2026-11-05")
    add("C", "planned")
    add("D", "rejected")
    active = apps(client, user)
    assert {i["title"] for i in active["items"]} == {"A", "B", "C"}
    assert active["counts"]["active"] == 3 and active["counts"]["closed"] == 1
    assert active["counts"]["by_status"]["interviewing"] == 1 and active["counts"]["by_status"]["offer"] == 0
    assert [i["title"] for i in apps(client, user, sort="next_step")["items"]] == ["B", "A", "C"]
    assert [i["title"] for i in apps(client, user, view="closed")["items"]] == ["D"]
    assert [i["title"] for i in apps(client, user, view="planned")["items"]] == ["C"]
    assert apps(client, user, view="all")["total"] == 4
    assert [i["title"] for i in apps(client, user, view="all", q="b")["items"]] == ["B"]
    assert client.get("/applications", headers=auth(user.id), params={"view": "nonsense"}).status_code == 422


def test_csv_export(client, sessions, user):
    item = first_match(client, sessions, user)
    client.post("/applications", headers=auth(user.id), json={"user_job_id": item["id"]})
    client.post("/applications", headers=auth(user.id), json={
        "title": "=HYPERLINK(\"http://evil.example\")", "company": "+44 Ltd", "notes": "@SUM(1)\nsecond line", "status": "planned"})
    response = client.get("/applications/export.csv", headers=auth(user.id))
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == f'attachment; filename="job-hunter-applications-{dt.date.today()}.csv"'
    assert response.content.startswith("﻿".encode())
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:4] == ["Company", "Job title", "Location", "Status"]
    by_title = {row[1]: row for row in rows[1:]}
    tracked = by_title["Staff Nurse - Acute Medicine"]
    assert (tracked[0], tracked[3], tracked[4], tracked[9]) == ("Contoso Health", "Applied", TODAY, "Sample jobs")
    hand = by_title["'=HYPERLINK(\"http://evil.example\")"]  # can't run as a formula
    assert hand[0] == "'+44 Ltd" and hand[8] == "'@SUM(1)\nsecond line" and hand[9] == "Added by hand"


@pytest.mark.parametrize("value, safe", [("=1+1", "'=1+1"), ("-2", "'-2"), ("@x", "'@x"), ("+x", "'+x"),
                                         ("\tx", "'\tx"), ("plain", "plain"), (None, ""), ("a=b", "a=b")])
def test_safe_cells(value, safe):
    assert safe_cell(value) == safe


def test_a_closed_job_is_marked_and_the_application_stays(client, sessions, user):
    item = first_match(client, sessions, user)
    app_id = client.post("/applications", headers=auth(user.id), json={"user_job_id": item["id"]}).json()["id"]
    with sessions() as session:
        job = session.get(Job, item["job"]["id"])
        job.closed_at = dt.datetime.now(dt.UTC)
        session.commit()
    app = client.get(f"/applications/{app_id}", headers=auth(user.id)).json()
    assert app["job_closed"] and app["title"] == "Staff Nurse - Acute Medicine"


def test_deleting_and_nobody_elses(client, sessions, user):
    app_id = client.post("/applications", headers=auth(user.id), json={"title": "Mine"}).json()["id"]
    with sessions() as session:
        other = User(email="kim@example.com", name="Kim")
        session.add(other)
        session.commit()
        other_id = other.id
    for method, path, body in (("GET", f"/applications/{app_id}", None), ("PATCH", f"/applications/{app_id}", {"notes": "x"}),
                               ("DELETE", f"/applications/{app_id}", None)):
        assert client.request(method, path, headers=auth(other_id), json=body).status_code == 404
    assert apps(client, User(id=other_id), view="all")["total"] == 0
    assert "Mine" not in client.get("/applications/export.csv", headers=auth(other_id)).text
    assert client.get("/applications").status_code == 401

    assert client.delete(f"/applications/{app_id}", headers=auth(user.id)).status_code == 204
    with sessions() as session:
        assert session.query(Application).count() == 0 and session.query(ApplicationEvent).count() == 0


def test_statuses_come_with_the_presets(client, user):
    statuses = client.get("/presets", headers=auth(user.id)).json()["application_statuses"]
    assert statuses[0] == {"key": "planned", "label": "To apply"} and len(statuses) == 8
