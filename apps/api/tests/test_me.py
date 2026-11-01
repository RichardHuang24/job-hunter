"""The signed-in user's profile, target roles, onboarding and title checks -
and nobody else's."""

from __future__ import annotations

from app.db.models import User
from tests.conftest import auth

NURSE_PROFILE = {
    "display_name": "  Alex  ", "headline": "Registered nurse", "summary": "Ward nurse moving into research.",
    "industry": "healthcare", "market": "uk", "years_experience": 4,
    "seniority_levels": ["senior", "mid"], "skills": ["Wound care", "wound care", " Phlebotomy "],
    "languages": [{"name": "Spanish", "level": "conversational"}],
    "locations": ["Manchester", "Remote (UK)"], "work_arrangements": ["remote", "onsite"],
    "authorized_countries": ["gb", "IE"], "open_to_sponsorship": True,
    "salary_min": 32000, "salary_currency": "gbp", "salary_period": "year",
}


def _other(sessions) -> User:
    with sessions() as session:
        other = User(email="sam@example.com")
        session.add(other)
        session.commit()
        return other


def test_me_without_a_profile_yet(client, user):
    assert client.get("/me", headers=auth(user.id)).json() == {
        "id": user.id, "email": "alex@example.com", "name": "Alex Example", "is_admin": False, "profile": None, "targets": [],
    }


def test_saving_and_reading_the_profile(client, user):
    saved = client.put("/me/profile", headers=auth(user.id), json=NURSE_PROFILE)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["display_name"] == "Alex" and body["onboarded_at"] is None
    assert body["seniority_levels"] == ["mid", "senior"]  # in level order
    assert body["skills"] == ["Wound care", "Phlebotomy"]  # trimmed, repeats dropped
    assert body["work_arrangements"] == ["onsite", "remote"]
    assert body["authorized_countries"] == ["GB", "IE"] and body["salary_currency"] == "GBP"
    assert body["updated_at"].endswith(("Z", "+00:00"))
    assert client.get("/me", headers=auth(user.id)).json()["profile"]["languages"] == [
        {"name": "Spanish", "level": "conversational"}]


def test_profile_values_must_come_from_the_presets(client, user):
    for bad in ({"industry": "astrology"}, {"market": "mars"}, {"seniority_levels": ["boss"]},
                {"work_arrangements": ["beach"]}, {"authorized_countries": ["XX"]},
                {"salary_min": 30000}, {"salary_min": 1, "salary_currency": "BTC"},
                {"salary_period": "fortnight"}, {"languages": [{"name": "French", "level": "fluent-ish"}]},
                {"favourite_colour": "blue"}, {"years_experience": -1}):
        response = client.put("/me/profile", headers=auth(user.id), json=bad)
        assert response.status_code == 422, bad
    assert client.put("/me/profile", headers=auth(user.id), json={"industry": "", "market": ""}).status_code == 200


def test_target_roles_are_replaced_in_order(client, user):
    first = client.put("/me/targets", headers=auth(user.id), json=[
        {"label": "Research nurse", "titles": ["Research Nurse", "clinical-research nurse"], "exclude": ["Student"]},
        {"label": "Staff nurse", "titles": ["staff nurse"], "search": ["staff nurse", "Staff Nurse"]},
    ])
    assert first.status_code == 200, first.text
    research, staff = first.json()
    assert research["titles"] == ["research nurse", "clinical research nurse"] and research["exclude"] == ["student"]
    assert research["search"] == ["Research nurse"]  # defaults to the label
    assert staff["search"] == ["staff nurse"] and [research["position"], staff["position"]] == [0, 1]

    second = client.put("/me/targets", headers=auth(user.id), json=[{"label": "Staff nurse", "titles": ["staff nurse"]}])
    assert [t["label"] for t in second.json()] == ["Staff nurse"]
    assert [t["label"] for t in client.get("/me", headers=auth(user.id)).json()["targets"]] == ["Staff nurse"]


def test_target_roles_are_checked(client, user):
    for bad in ([{"label": "Nurse", "titles": []}], [{"label": "", "titles": ["nurse"]}],
                [{"label": "Nurse", "titles": ["nurse"], "preset_role": "healthcare/astronaut"}],
                [{"label": f"Role {i}", "titles": [f"role {i}"]} for i in range(13)]):
        assert client.put("/me/targets", headers=auth(user.id), json=bad).status_code == 422, bad


def test_onboarding_sets_up_profile_and_roles(client, user):
    response = client.post("/me/onboarding", headers=auth(user.id), json={
        **NURSE_PROFILE, "roles": ["registered-nurse", "midwife", "registered-nurse"],
        "custom_roles": [{"label": "Research nurse", "titles": ["research nurse"]}],
    })
    assert response.status_code == 200, response.text
    me = response.json()
    assert me["profile"]["onboarded_at"] is not None
    assert [t["label"] for t in me["targets"]] == ["Registered nurse", "Midwife", "Research nurse"]
    nurse = me["targets"][0]
    assert nurse["preset_role"] == "healthcare/registered-nurse" and "staff nurse" in nurse["titles"]

    again = client.post("/me/onboarding", headers=auth(user.id), json={**NURSE_PROFILE, "roles": ["doctor"]}).json()
    assert [t["label"] for t in again["targets"]] == ["Doctor"]
    assert again["profile"]["onboarded_at"] == me["profile"]["onboarded_at"]  # the first run's time stays


def test_onboarding_needs_the_essentials(client, user):
    base = {**NURSE_PROFILE, "roles": ["registered-nurse"]}
    for bad in ({**base, "market": ""}, {**base, "industry": ""}, {**base, "roles": []},
                {**base, "roles": ["astronaut"]}, {**base, "industry": "legal"}):
        assert client.post("/me/onboarding", headers=auth(user.id), json=bad).status_code == 422, bad
    assert client.get("/me", headers=auth(user.id)).json()["profile"] is None  # nothing half-saved


def test_title_check_explains_the_verdict(client, user):
    client.post("/me/onboarding", headers=auth(user.id), json={**NURSE_PROFILE, "roles": ["registered-nurse"]})

    def check(title):
        return client.post("/me/title-check", headers=auth(user.id), json={"title": title}).json()

    wanted = check("Senior Staff Nurse - Band 6")
    assert wanted["wanted"] and wanted["target"]["label"] == "Registered nurse"
    assert (wanted["matched"], wanted["level"]["key"]) == ("staff nurse", "senior")
    assert "Registered nurse" in wanted["explanation"]

    too_senior = check("Ward Sister")
    assert not too_senior["wanted"] and too_senior["target"] is None

    lead = check("Charge Nurse")
    assert lead["target"]["label"] == "Registered nurse" and not lead["wanted"]
    assert "mid level or senior" in lead["explanation"]

    assert not check("Primary Teacher")["wanted"]
    assert client.post("/me/title-check", headers=auth(user.id), json={"title": " "}).status_code == 422


def test_title_check_without_a_profile(client, user):
    body = client.post("/me/title-check", headers=auth(user.id), json={"title": "Senior Nurse"}).json()
    assert body["target"] is None and body["level"]["key"] == "senior" and not body["wanted"]


def test_one_user_never_sees_or_changes_another_users_data(client, sessions, user):
    other = _other(sessions)
    client.post("/me/onboarding", headers=auth(user.id), json={**NURSE_PROFILE, "roles": ["registered-nurse"]})
    assert client.get("/me", headers=auth(other.id)).json() == {
        "id": other.id, "email": "sam@example.com", "name": None, "is_admin": False, "profile": None, "targets": []}
    client.put("/me/targets", headers=auth(other.id), json=[{"label": "Chef", "titles": ["chef"]}])
    mine = client.get("/me", headers=auth(user.id)).json()["targets"]
    assert [t["label"] for t in mine] == ["Registered nurse"]
    assert not client.post("/me/title-check", headers=auth(other.id), json={"title": "Staff Nurse"}).json()["wanted"]
