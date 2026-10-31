"""One real call to Claude - skipped unless you ask for it, so tests never
spend money by accident:

    RUN_LIVE_AI=1 ANTHROPIC_API_KEY=sk-... pytest tests/test_scoring_live.py
"""

from __future__ import annotations

import os

import pytest

LIVE_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # read before the test fixtures blank it
pytestmark = pytest.mark.skipif(not (os.environ.get("RUN_LIVE_AI") == "1" and LIVE_KEY),
                                reason="set RUN_LIVE_AI=1 and ANTHROPIC_API_KEY to call the real API")


def test_one_real_score():
    import anthropic

    from app.config import Settings
    from app.scoring.providers import AnthropicScorer
    from tests.test_scoring_providers import REQUEST

    model = os.environ.get("AI_MODEL", "claude-opus-5-5")
    scorer = AnthropicScorer(anthropic.Anthropic(api_key=LIVE_KEY, timeout=120), model, "low", Settings())
    result = scorer.score(REQUEST)
    assert 0 <= result.analysis.scores.skills.score <= 100
    assert result.usage.output_tokens > 0 and result.cost_usd > 0
    print(f"\n{result.model}: {result.usage} -> ${result.cost_usd}")
