"""The signed-in user and their profile - and nobody else's."""

from __future__ import annotations

from app.db.models import User
from tests.conftest import auth


def test_me_without_a_profile_yet(client, user):
    assert client.get("/me", headers=auth(user.id)).json() == {
        "id": user.id, "email": "alex@example.com", "name": "Alex Example", "profile": None,
    }


def test_saving_and_reading_the_profile(client, user):
    saved = client.put("/me/profile", headers=auth(user.id), json={
        "display_name": "  Alex  ", "headline": "Registered nurse", "industry": "healthcare", "market": "uk",
    })
    assert saved.status_code == 200
    body = saved.json()
    assert (body["display_name"], body["industry"]) == ("Alex", "healthcare")
    assert body["updated_at"].endswith(("Z", "+00:00"))
    assert client.get("/me", headers=auth(user.id)).json()["profile"]["headline"] == "Registered nurse"


def test_industry_and_market_must_be_presets(client, user):
    for bad in ({"industry": "Health Care!"}, {"industry": "astrology"}, {"market": "mars"}):
        assert client.put("/me/profile", headers=auth(user.id), json=bad).status_code == 422
    assert client.put("/me/profile", headers=auth(user.id), json={"industry": "", "market": ""}).status_code == 200


def test_presets_list_every_choice(client, user):
    body = client.get("/presets", headers=auth(user.id)).json()
    assert {"key": "healthcare", "label": "Healthcare"} in body["industries"]
    assert {"key": "uk", "label": "United Kingdom"} in body["markets"]
    assert client.get("/presets").status_code == 401


def test_one_user_never_sees_another_users_profile(client, sessions, user):
    with sessions() as session:
        other = User(email="sam@example.com")
        session.add(other)
        session.commit()
    client.put("/me/profile", headers=auth(user.id), json={"headline": "Registered nurse"})
    assert client.get("/me", headers=auth(other.id)).json()["profile"] is None
