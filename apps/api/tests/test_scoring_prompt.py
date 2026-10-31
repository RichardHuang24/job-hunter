"""The scoring request and answer - pure parts."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.presets import get_catalog
from app.scoring.prompt import (
    Analysis,
    Dimension,
    answer_schema,
    band_for,
    candidate_block,
    check_evidence,
    inputs_hash,
    parse_answer,
    quote_in,
    user_message,
    weighted_overall,
)

ANSWER = {
    "summary": "A ward nurse role on acute medicine.",
    "scores": {"skills": {"score": 80, "reason": "r"}, "experience": {"score": 70, "reason": "r"},
               "culture": {"score": 60, "reason": "r"}, "career": {"score": 90, "reason": "r"}},
    "matched": [{"requirement": "NMC registration", "detail": "Profile lists it"},
                {"requirement": "ten years of oncology", "detail": "Made up"}],
    "missing": [{"requirement": "IV-trained", "kind": "required", "note": "Not mentioned"}],
    "risks": ["Night shifts"], "unclear": ["Parking"],
}
POSTING = "Staff Nurse\\nWe need an **NMC registration** and you must be IV‑trained. Night shifts apply."


def test_the_schema_is_strict_everywhere():
    def walk(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False and set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)
        elif node.get("type") == "array":
            walk(node["items"])
    schema = answer_schema()
    walk(schema)
    assert set(schema["properties"]["scores"]["properties"]) == {"skills", "experience", "culture", "career"}
    assert "minimum" not in json.dumps(schema)  # structured outputs take no number ranges


def test_quotes_are_checked_against_the_posting():
    assert quote_in("NMC registration", POSTING)
    assert quote_in("you must be IV-trained.", POSTING)  # dashes, case and trailing punctuation ignored
    assert quote_in("We need ... night shifts", POSTING)  # parts around an ellipsis, in order
    assert not quote_in("night shifts ... We need", POSTING)
    assert not quote_in("ten years of oncology", POSTING)
    assert not quote_in("an", POSTING)  # too short to count
    analysis = check_evidence(parse_answer(json.dumps(ANSWER)), POSTING)
    assert [m.verified for m in analysis.matched] == [True, False]
    assert analysis.missing[0].verified


def test_scores_out_of_range_are_rejected():
    bad = json.loads(json.dumps(ANSWER))
    bad["scores"]["skills"]["score"] = 140
    with pytest.raises(ValueError):
        parse_answer(json.dumps(bad))


def test_the_overall_score_is_weighted_by_the_industry():
    analysis = Analysis.model_validate(ANSWER)
    healthcare = get_catalog().industries["healthcare"].scoring  # skills 30, experience 35, culture 15, career 20
    assert weighted_overall(analysis, healthcare) == round((80 * 30 + 70 * 35 + 60 * 15 + 90 * 20) / 100)
    assert weighted_overall(analysis, {"skills": 100}) == 80
    bands = get_catalog().bands
    assert [band_for(s, bands).label for s in (100, 75, 74, 45, 0)] == ["Strong fit", "Strong fit", "Good fit", "Possible fit", "Poor fit"]


def test_the_candidate_and_the_posting_as_the_model_reads_them():
    profile = SimpleNamespace(headline="Registered nurse", seniority_levels=["mid", "senior"], years_experience=4,
                              skills=["Wound care"], languages=[{"name": "Spanish", "level": "conversational"}],
                              summary="Moving into research.")
    targets = [SimpleNamespace(label="Registered nurse", titles=["staff nurse", "registered nurse"])]
    block = candidate_block(profile, targets, industry="Healthcare", market="United Kingdom",
                            levels={"mid": "Mid level", "senior": "Senior"},
                            dimensions=[Dimension("skills", "Skills", "Skills asked for.", 30)])
    for text in ("<candidate>", "Registered nurse (titles like staff nurse, registered nurse)", "Mid level, Senior",
                 "Years of experience: 4", "Spanish (conversational)", "Moving into research.", "skills (Skills, 30%)"):
        assert text in block, text
    message = user_message(title="Staff Nurse", company="Contoso Health", location="Manchester",
                           checks=[{"key": "salary", "status": "flag", "detail": "Below your minimum"}], description="Ward job.")
    assert "<posting>\nWard job.\n</posting>" in message and "- salary: flag - Below your minimum" in message
    assert inputs_hash("a", "b") != inputs_hash("a", "c") and len(inputs_hash("a", "b")) == 32
