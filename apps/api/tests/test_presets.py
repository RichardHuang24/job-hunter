"""The presets in presets/ load, hold together, and are served."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.matching.titles import match_title
from app.presets import PresetError, get_catalog, load_catalog
from app.presets.catalog import presets_dir
from tests.conftest import auth


def test_every_preset_loads():
    catalog = get_catalog()
    assert len(catalog.industries) >= 10 and len(catalog.markets) >= 5
    assert catalog.level_keys[0] == "intern" and "mid" in catalog.level_keys
    assert {"GB", "US", "DE"} <= set(catalog.countries)


@pytest.mark.parametrize("industry", sorted(get_catalog().industries))
def test_each_role_is_found_by_its_own_titles_and_searches(industry):
    """A role's own titles and search terms, read as job titles, land on that
    role - so no role in an industry is shadowed by another."""
    catalog = get_catalog()
    roles = catalog.industries[industry].roles
    for role in roles:
        for title in (*role.titles, *role.search):
            found = match_title(title, roles, catalog.levels_for(industry)).target
            assert found is not None and found.key == role.key, f"{industry}: {title!r} -> {found and found.key}"


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "presets"
    shutil.copytree(presets_dir(), root)
    return root


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, old
    path.write_text(text.replace(old, new, 1))


@pytest.mark.parametrize("file,old,new,message", [
    ("industries/healthcare.toml", "skills = 30", "skills = 31", "add up to 100"),
    ("industries/healthcare.toml", "skills = 30", "skils = 30", "exactly these dimensions"),
    ("industries/healthcare.toml", "[seniority]", "[seniority]\nboss = [\"boss\"]", "no level called boss"),
    ("industries/healthcare.toml", 'key = "midwife"', 'key = "doctor"', "listed twice"),
    ("industries/healthcare.toml", 'label = "Healthcare"', 'label = "Healthcare"\ncolour = "blue"', "Extra inputs"),
    ("industries/healthcare.toml", '"nurse", "rgn"', '"nurse", "Nurse"', "listed twice"),
    ("markets/uk.toml", 'currency = "GBP"', 'currency = "pounds"', "currency"),
    ("markets/uk.toml", 'salary_period = "year"', 'salary_period = "fortnight"', "salary_period"),
    ("markets/ie.toml", 'IE = "Ireland"', 'IE = "Eire"', "called"),
    ("scoring.toml", "min = 0", "min = 5", "min = 0"),
])
def test_an_inconsistent_preset_is_refused(tmp_path, file, old, new, message):
    root = _copy(tmp_path)
    _edit(root / file, old, new)
    with pytest.raises(PresetError, match=message):
        load_catalog(root)


def test_a_badly_named_file_is_refused(tmp_path):
    root = _copy(tmp_path)
    (root / "industries" / "healthcare.toml").rename(root / "industries" / "Health Care.toml")
    with pytest.raises(PresetError, match="file names"):
        load_catalog(root)


def test_the_option_lists_are_served(client, user):
    body = client.get("/presets", headers=auth(user.id)).json()
    assert {"key": "healthcare", "label": "Healthcare", "description": body["industries"][[i["key"] for i in body["industries"]].index("healthcare")]["description"]} in body["industries"]
    assert {"key": "uk", "label": "United Kingdom", "currency": "GBP"} in body["markets"]
    assert [lv["key"] for lv in body["levels"]][:3] == ["intern", "entry", "mid"]
    assert {"key": "GB", "label": "United Kingdom"} in body["countries"]
    assert "EUR" in body["currencies"] and {"key": "remote", "label": "Remote"} in body["arrangements"]
    assert client.get("/presets").status_code == 401


def test_an_industry_and_a_market_in_full(client, user):
    nursing = client.get("/presets/industries/healthcare", headers=auth(user.id)).json()
    nurse = next(r for r in nursing["roles"] if r["key"] == "registered-nurse")
    assert "staff nurse" in nurse["titles"] and nurse["search"]
    assert sum(d["weight"] for d in nursing["scoring"]) == 100
    assert "band 7" in nursing["seniority"]["lead"]
    uk = client.get("/presets/markets/uk", headers=auth(user.id)).json()
    assert uk["currency"] == "GBP" and "Manchester" in uk["locations"]
    assert client.get("/presets/industries/astrology", headers=auth(user.id)).status_code == 404
    assert client.get("/presets/markets/mars", headers=auth(user.id)).status_code == 404
