"""The industries and job markets a profile can pick from.

Each will grow its own search terms, title rules and scoring rubric
(docs/roadmap.md); for now they are the keys a profile stores. Add one by
appending a (key, label) pair - keys are lowercase words joined by hyphens
and never change once used, since profiles store them.
"""

from __future__ import annotations

INDUSTRIES: tuple[tuple[str, str], ...] = (
    ("software-engineering", "Software engineering"),
    ("data-ai", "Data & AI"),
    ("product-design", "Product & design"),
    ("finance", "Finance & accounting"),
    ("healthcare", "Healthcare"),
    ("education", "Education"),
    ("marketing", "Marketing & communications"),
    ("sales", "Sales & customer success"),
    ("operations", "Operations & supply chain"),
    ("engineering", "Engineering (civil, mechanical, electrical)"),
    ("legal", "Legal"),
    ("hospitality", "Hospitality & retail"),
)

MARKETS: tuple[tuple[str, str], ...] = (
    ("uk", "United Kingdom"),
    ("ie", "Ireland"),
    ("us", "United States"),
    ("ca", "Canada"),
    ("eu", "European Union"),
    ("au", "Australia"),
    ("remote", "Remote (anywhere)"),
)

INDUSTRY_KEYS = frozenset(key for key, _ in INDUSTRIES)
MARKET_KEYS = frozenset(key for key, _ in MARKETS)
