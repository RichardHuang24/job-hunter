"""Reading job titles: which target role, and what level."""

from __future__ import annotations

import pytest

from app.matching.titles import match_title, normalize
from app.presets import get_catalog


def test_normalize():
    assert normalize("  Front-End Developer (UK) ") == "front end developer uk"
    assert normalize("C++ / C# Engineer") == "c++ c# engineer"
    assert normalize("FP&A Analyst") == "fp&a analyst"
    assert normalize("Ingénieur logiciel") == "ingénieur logiciel"


@pytest.mark.parametrize("industry,title,role,level", [
    ("healthcare", "Senior Staff Nurse (Band 6)", "registered-nurse", "senior"),
    ("healthcare", "Staff Nurse - Band 5", "registered-nurse", "entry"),
    ("healthcare", "Charge Nurse", "registered-nurse", "lead"),
    ("healthcare", "Nursery Nurse", None, "mid"),
    ("healthcare", "Student Nurse", None, "mid"),
    ("education", "Head of Year 9", None, "lead"),
    ("education", "Assistant Headteacher", None, "manager"),
    ("education", "Senior Lecturer in Law", "lecturer", "senior"),
    ("hospitality", "Sous Chef", "chef", "lead"),
    ("hospitality", "Commis Chef", "chef", "entry"),
    ("marketing", "Lead Generation Marketing Executive", "marketing", "mid"),
    ("product-design", "Senior Product Manager", "product-manager", "senior"),
    ("product-design", "Product Manager", "product-manager", "mid"),
    ("software-engineering", "Staff Software Engineer", "software-engineer", "lead"),
    ("software-engineering", "Front-End Developer", "frontend-engineer", "mid"),
    ("software-engineering", "Business Developer", None, "mid"),
    ("software-engineering", "Graduate Software Engineer", "software-engineer", "entry"),
    ("legal", "Trainee Solicitor", "solicitor", "entry"),
    ("legal", "Partner, Employment", None, "executive"),
    ("finance", "Audit Senior", "auditor", "senior"),
    ("finance", "Audit Manager", "auditor", "manager"),
    ("finance", "FP&A Analyst", "financial-analyst", "mid"),
    ("finance", "Summer Analyst Programme", None, "intern"),
    ("data-ai", "Head of Data Science", None, "executive"),
    ("operations", "Database Administrator", None, "mid"),
])
def test_titles_in_each_industry(industry, title, role, level):
    catalog = get_catalog()
    roles = catalog.industries[industry].roles
    result = match_title(title, roles, catalog.levels_for(industry))
    assert (result.target.key if result.target else None, result.level) == (role, level)


def test_the_longest_matching_phrase_picks_the_target():
    roles = get_catalog().industries["software-engineering"].roles
    result = match_title("Senior Full Stack Developer", roles, get_catalog().levels)
    assert (result.target.key, result.phrase, result.level_words) == ("full-stack-engineer", "full stack developer", ("senior",))


def test_industry_words_only_count_in_their_industry():
    catalog = get_catalog()
    roles = catalog.industries["healthcare"].roles
    assert match_title("Staff Nurse Band 7", roles, catalog.levels_for("healthcare")).level == "lead"
    assert match_title("Staff Nurse Band 7", roles, catalog.levels).level == "mid"
