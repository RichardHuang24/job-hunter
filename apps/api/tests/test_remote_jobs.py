"""Remote jobs end to end: where they're open, the permit check, and taking
down jobs that close or expire - with stand-in sources, no network."""

from __future__ import annotations

import datetime as dt

from app.countries import NAMES, REGIONS, code_for, parse_places
from app.db.models import Job, Task
from app.search.recheck import queue_recheck, recheck_due
from app.sources.base import Posting, Query, Source
from tests.conftest import auth
from tests.test_evaluate import Job as FakeJob
from tests.test_evaluate import Profile, run
from tests.test_search import jobs, onboard, titles, work

NOW = dt.datetime.now(dt.UTC)


def test_country_names_and_regions():
    assert len(NAMES) == 250 and all(len(code) == 2 and code.isupper() for code in NAMES)
    assert all(code in NAMES for codes in REGIONS.values() for code in codes)
    for name, code in [("UK", "GB"), ("United Kingdom", "GB"), ("usa", "US"), ("Türkiye", "TR"), ("Côte d’Ivoire", "CI"),
                       ("Korea, Republic of", "KR"), ("Congo, The Democratic Republic of the", "CD"), ("de", "DE"),
                       ("Czech Republic", "CZ"), ("Viet Nam", "VN"), ("Atlantis", "")]:
        assert code_for(name) == code, name
    places = parse_places(["Canada", " USA ", "Europe", "Narnia", "Canada", ""])
    assert places.codes[:2] == ("CA", "US") and "GB" in places.codes and "DE" in places.codes
    assert len(places.codes) == len(set(places.codes)) and places.unknown == ("Narnia",) and not places.worldwide
    assert parse_places(["Anywhere"]).worldwide and parse_places(["Worldwide"]).codes == ()


def test_the_permit_check_for_remote_jobs():
    remote = dict(arrangement="remote", location="Remote", country="")
    assert run(FakeJob(**remote, worldwide=True))[1]["permit"] == ("pass", "Open to people anywhere")
    assert run(FakeJob(**remote, countries=("US", "GB")))[1]["permit"] == ("pass", "United Kingdom - no visa needed")
    assert run(FakeJob(**remote, countries=("US", "CA")))[1]["permit"] == ("fail", "United States and Canada - you’d need a visa")
    assert run(FakeJob(**remote, countries=("NG", "KE", "GH", "ZA")))[1]["permit"] == (
        "fail", "Nigeria, Kenya and 2 more - you’d need a visa")  # names beyond the presets' markets
    assert run(FakeJob(**remote, countries=("US",)), Profile(open_to_sponsorship=True))[1]["permit"][0] == "flag"
    assert run(FakeJob(**remote))[1]["permit"] == ("unknown", "The posting doesn’t say which country")
    assert run(FakeJob())[1]["permit"] == ("pass", "United Kingdom - no visa needed")  # one country, as before


class RemoteBoard(Source):
    """Remote jobs only, with places, expiry dates and a status check."""

    key, label, description, homepage, commercial, remote_only = "board", "Board", "Remote jobs", "https://board.example", True, True
    check_every = dt.timedelta(hours=1)
    closed: set[str] = set()
    asked: list[list[str]] = []

    def search(self, query: Query) -> list[Posting]:
        common = dict(arrangement="remote", posted_at=NOW, description="Remote nursing. What you'll need: triage.")
        return [
            Posting("uk", "https://board.example/uk", "Staff Nurse - Remote Triage", "Calder Health",
                    "Remote (United Kingdom)", "GB", countries=("GB",), expires_at=NOW + dt.timedelta(days=20), **common),
            Posting("us", "https://board.example/us", "Staff Nurse - Telehealth", "Prairie Care",
                    "Remote (United States, Canada)", countries=("US", "CA"), **common),
            Posting("any", "https://board.example/any", "Staff Nurse - Virtual Ward", "Open Ward",
                    "Remote (anywhere)", worldwide=True, **common),
        ]

    def check(self, jobs):
        RemoteBoard.asked.append([source_id for source_id, _ in jobs])
        return {source_id: "closed" if source_id in self.closed else "open" for source_id, _ in jobs}


def onboard_remote(client, sessions, user, monkeypatch):
    from app.search import runs

    from app.sources import SOURCES

    RemoteBoard.closed, RemoteBoard.asked = set(), []
    monkeypatch.setitem(SOURCES, "board", RemoteBoard)
    monkeypatch.setattr(runs, "enabled_sources", lambda: [RemoteBoard()])
    onboard(client, user, work_arrangements=["remote", "hybrid"], locations=["Manchester"])
    work(sessions)


def test_remote_jobs_are_stored_with_their_places(client, sessions, user, monkeypatch):
    onboard_remote(client, sessions, user, monkeypatch)
    [search] = client.get("/searches", headers=auth(user.id)).json()
    assert search["include_remote"]  # open to remote work, so the search asks remote-only sources too
    assert search["last_run"]["status"] == "queued" or search["last_run"]["counts"]["by_source"] == {"board": 3}
    with sessions() as session:
        uk = session.query(Job).filter_by(source="board", source_id="uk").one()
        assert (uk.countries, uk.worldwide, uk.closed_at) == (["GB"], False, None)
        assert uk.expires_at is not None and uk.checked_at is not None
    listing = jobs(client, user)
    assert titles(listing) == {"Staff Nurse - Remote Triage", "Staff Nurse - Virtual Ward"}
    assert titles(jobs(client, user, "filtered")) == {"Staff Nurse - Telehealth"}  # US/Canada only
    item = listing["items"][0]["job"]
    assert item["source_label"] == "Board" and item["source_url"] == "https://board.example" and not item["closed"]


def test_a_remote_job_on_two_boards_is_shown_once(client, sessions, user, monkeypatch):
    from app.search import runs

    class OtherBoard(RemoteBoard):
        key = "other"

        def search(self, query):
            return [Posting("x1", "https://other.example/x1", "Staff Nurse - Remote Triage", "Calder Health",
                            "Remote (UK)", "GB", "remote", countries=("GB",))]
    monkeypatch.setattr(runs, "enabled_sources", lambda: [RemoteBoard(), OtherBoard()])
    onboard(client, user, work_arrangements=["remote"], locations=["Remote (UK)"])
    work(sessions)
    listed = [i for i in jobs(client, user)["items"] if i["job"]["title"] == "Staff Nurse - Remote Triage"]
    assert len(listed) == 1  # "Remote (United Kingdom)" on one board, "Remote (UK)" on the other


def test_remote_only_sources_skip_place_searches(client, sessions, user, monkeypatch):
    from app.search import runs

    monkeypatch.setattr(runs, "enabled_sources", lambda: [RemoteBoard()])
    onboard(client, user)  # on-site and hybrid only: no remote query
    work(sessions)
    [search] = client.get("/searches", headers=auth(user.id)).json()
    assert not search["include_remote"] and jobs(client, user)["counts"]["matches"] == 0


def test_closed_and_expired_jobs_come_down(client, sessions, user, monkeypatch):
    onboard_remote(client, sessions, user, monkeypatch)
    listing = jobs(client, user)
    virtual = next(i for i in listing["items"] if i["job"]["title"] == "Staff Nurse - Virtual Ward")
    triage = next(i for i in listing["items"] if i["job"]["title"] == "Staff Nurse - Remote Triage")
    client.patch(f"/jobs/{virtual['id']}", headers=auth(user.id), json={"state": "saved"})

    RemoteBoard.closed = {"any"}
    assert recheck_due_now(sessions, now=NOW + dt.timedelta(hours=2)) == {"board": {"open": 2, "closed": 1}}
    with sessions() as session:  # and the triage job expires
        session.query(Job).filter_by(source_id="uk").one().expires_at = NOW - dt.timedelta(minutes=1)
        session.commit()

    after = jobs(client, user)
    assert after["items"] == [] and after["counts"]["matches"] == 0 and after["counts"]["saved"] == 1
    [saved] = jobs(client, user, "saved")["items"]
    assert saved["job"]["closed"] and saved["id"] == virtual["id"]
    detail = client.get(f"/jobs/{virtual['id']}", headers=auth(user.id)).json()
    assert detail["job"]["closed"] and detail["job"]["description"] == ""  # the posting comes down
    assert client.post(f"/jobs/{triage['id']}/score", headers=auth(user.id)).status_code == 410

    work(sessions)  # a fresh search lists the triage job again (with a new date) - it's open
    client.post(f"/searches/{client.get('/searches', headers=auth(user.id)).json()[0]['id']}/run", headers=auth(user.id))
    work(sessions)
    assert "Staff Nurse - Remote Triage" in titles(jobs(client, user))


def recheck_due_now(sessions, **kwargs):
    with sessions() as session:
        return recheck_due(session, [RemoteBoard()], **kwargs)


def test_rechecks_are_spaced_and_only_for_jobs_people_have(client, sessions, user, monkeypatch):
    onboard_remote(client, sessions, user, monkeypatch)
    with sessions() as session:  # a job nobody has
        session.add(Job(source="board", source_id="orphan", url="https://board.example/o", title="X", fingerprint="o"))
        session.commit()
    assert recheck_due_now(sessions) == {}  # just checked by the search itself
    later = NOW + dt.timedelta(hours=2)
    assert recheck_due_now(sessions, now=later) == {"board": {"open": 3}}
    assert sorted(RemoteBoard.asked[-1]) == ["any", "uk", "us"]
    assert recheck_due_now(sessions, now=later + dt.timedelta(minutes=30)) == {}

    class Broken(RemoteBoard):
        def check(self, jobs):
            raise TimeoutError("board didn't answer")
    with sessions() as session:
        assert recheck_due(session, [Broken()], now=later + dt.timedelta(hours=2)) == {
            "board": {"error": "TimeoutError: board didn't answer"}}


def test_the_worker_queues_one_recheck_at_a_time(sessions, monkeypatch):
    from app.search import recheck

    with sessions() as session:
        assert not queue_recheck(session)  # only the demo source: nothing to check
    monkeypatch.setattr(recheck, "enabled_sources", lambda: [RemoteBoard()])
    with sessions() as session:
        assert queue_recheck(session)
        assert not queue_recheck(session)  # one is already waiting
        assert session.query(Task).filter_by(kind="recheck").count() == 1
    from app.tasks.handlers import HANDLERS
    assert "recheck" in HANDLERS
