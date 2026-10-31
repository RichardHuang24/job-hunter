"""The Claude scorer against a stand-in client, and the simulated scorer."""

from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.config import Settings
from app.scoring.providers import (
    AnthropicScorer,
    ScoreRequest,
    ScoringError,
    SimulatedScorer,
    Usage,
    describe,
    estimate_cost,
    get_scorer,
)
from tests.test_scoring_prompt import ANSWER, POSTING

REQUEST = ScoreRequest(system="SYSTEM", message="MESSAGE", posting=POSTING, skills=("NMC registration", "Phlebotomy"),
                       role="Registered nurse", level_wanted=True, arrangement_fits=None,
                       field_skills=("IV-trained", "Phlebotomy"), flags=("Salary below your minimum",), unknowns=("Hours",))


def response(text=json.dumps(ANSWER), stop="end_turn", model="claude-opus-5-5", usage=None, details=None):
    usage = usage or SimpleNamespace(input_tokens=1200, output_tokens=900, cache_read_input_tokens=3000,
                                     cache_creation_input_tokens=0, iterations=None)
    blocks = [SimpleNamespace(type="thinking", thinking="")] + ([SimpleNamespace(type="text", text=text)] if text else [])
    return SimpleNamespace(content=blocks, stop_reason=stop, stop_details=details, model=model, usage=usage)


class Client:
    """Records each call; answers with `reply` or raises it."""

    def __init__(self, reply):
        self.calls, self.reply = [], reply
        self.messages = SimpleNamespace(create=lambda **kw: self._call("messages", kw))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: self._call("beta", kw)))

    def _call(self, where, kwargs):
        self.calls.append((where, kwargs))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_the_request_to_claude():
    client = Client(response())
    result = AnthropicScorer(client, "claude-opus-5-5", "medium", Settings()).score(REQUEST)
    [(where, sent)] = client.calls
    assert where == "beta" and sent["betas"] == ["server-side-fallback-2026-07-01"] and sent["fallbacks"] == "default"
    assert sent["model"] == "claude-opus-5-5" and sent["max_tokens"] == 16_000
    assert sent["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
    assert sent["messages"] == [{"role": "user", "content": "MESSAGE"}]
    assert sent["output_config"]["effort"] == "medium" and sent["output_config"]["format"]["type"] == "json_schema"
    assert not {"temperature", "top_p", "top_k", "thinking"} & set(sent)
    assert result.provider == "anthropic" and result.analysis.scores.career.score == 90
    assert [m.verified for m in result.analysis.matched] == [True, False]
    # 1200 in at $4, 3000 cached at $0.40, 900 out at $20 - per million
    assert result.cost_usd == pytest.approx((1200 * 4 + 3000 * 0.4 + 900 * 20) / 1e6)


def test_haiku_has_no_server_side_fallback():
    client = Client(response(model="claude-haiku-5-5"))
    AnthropicScorer(client, "claude-haiku-5-5", "low", Settings()).score(REQUEST)
    [(where, sent)] = client.calls
    assert where == "messages" and "fallbacks" not in sent and "betas" not in sent


@pytest.mark.parametrize("model, effort, sent", [
    ("claude-haiku-5-5", "low", {"type": "disabled"}),
    ("claude-haiku-5-5", "high", {"type": "disabled"}),
    ("claude-haiku-5-5", "xhigh", None),  # thinking can't be off above high
    ("claude-sonnet-5-5", "low", {"type": "between_tools"}),
    ("claude-opus-5", "medium", {"type": "disabled"}),
    ("claude-opus-5-5", "low", None),  # always thinks
    ("claude-some-future-model", "low", None),  # unknown: left at its default
])
def test_thinking_off(model, effort, sent):
    params = AnthropicScorer(Client(response()), model, effort, Settings(), thinking=False).params(REQUEST)
    assert params.get("thinking") == sent
    assert "thinking" not in AnthropicScorer(Client(response()), model, effort, Settings()).params(REQUEST)


def test_the_default_is_the_cheapest_model_without_thinking():
    settings = Settings(anthropic_api_key="sk-test")
    scorer = get_scorer(settings)
    assert (settings.ai_model, settings.ai_effort, settings.ai_thinking) == ("claude-haiku-5-5", "low", False)
    assert scorer.params(REQUEST)["thinking"] == {"type": "disabled"}
    assert scorer.params(REQUEST)["output_config"]["effort"] == "low"


def test_a_fallback_is_billed_per_attempt():
    usage = SimpleNamespace(input_tokens=500, output_tokens=400, cache_read_input_tokens=0, cache_creation_input_tokens=0,
                            iterations=[
                                SimpleNamespace(type="message", model="claude-opus-5-5", input_tokens=500, output_tokens=0,
                                                cache_read_input_tokens=0, cache_creation_input_tokens=0),
                                SimpleNamespace(type="fallback_message", model="claude-opus-4-8", input_tokens=500,
                                                output_tokens=400, cache_read_input_tokens=0, cache_creation_input_tokens=0)])
    result = AnthropicScorer(Client(response(usage=usage, model="claude-opus-4-8")), "claude-opus-5-5", "medium", Settings()).score(REQUEST)
    assert result.model == "claude-opus-4-8" and result.usage.input_tokens == 1000
    assert result.cost_usd == pytest.approx((500 * 4 + 500 * 5 + 400 * 25) / 1e6)


@pytest.mark.parametrize("reply,code", [
    (response(stop="refusal", text="", details=SimpleNamespace(category="bio")), "refusal"),
    (response(stop="max_tokens"), "cut_off"),
    (response(text=""), "empty"),
    (response(text="{not json"), "invalid"),
    (response(text=json.dumps({**ANSWER, "scores": {}})), "invalid"),
])
def test_unusable_answers(reply, code):
    with pytest.raises(ScoringError) as raised:
        AnthropicScorer(Client(reply), "claude-opus-5-5", "medium", Settings()).score(REQUEST)
    assert raised.value.code == code and not raised.value.stop


def _status(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("failed", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize("error,code,stop", [
    (_status(anthropic.AuthenticationError, 401), "auth", True),
    (_status(anthropic.PermissionDeniedError, 403), "permission", True),
    (_status(anthropic.RateLimitError, 429), "rate_limited", True),
    (_status(anthropic.BadRequestError, 400), "bad_request", False),
    (_status(anthropic.InternalServerError, 500), "unavailable", True),
    (_status(anthropic.APIStatusError, 402), "api_error", True),
    (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), "unreachable", True),
])
def test_api_errors(error, code, stop):
    with pytest.raises(ScoringError) as raised:
        AnthropicScorer(Client(error), "claude-opus-5-5", "medium", Settings()).score(REQUEST)
    assert (raised.value.code, raised.value.stop) == (code, stop)


def test_costs():
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert estimate_cost("claude-opus-5-5", usage, Settings()) == 24.0
    assert estimate_cost("claude-haiku-5-5", Usage(input_tokens=50_000, output_tokens=10_000), Settings()) == 0.01
    assert estimate_cost("claude-haiku-5-5", usage, Settings()) == 3.0  # a 1M-token prompt is over 100K: long-prompt price
    assert estimate_cost("claude-haiku-5-5", Usage(input_tokens=200_000), Settings()) == 0.1  # long-prompt price
    assert estimate_cost("claude-unknown", usage, Settings()) == 0.0
    assert estimate_cost("claude-unknown", usage, Settings(ai_price_input=1, ai_price_output=2)) == 3.0


def test_the_simulated_scorer():
    result = SimulatedScorer().score(REQUEST)
    analysis = result.analysis
    assert result.provider == "simulated" and result.cost_usd == 0
    assert analysis.scores.skills.score == 40 + round(55 * 1 / 2)  # NMC registration found, Phlebotomy not
    assert analysis.scores.experience.score == 80 and analysis.scores.career.score == 78
    assert all(getattr(analysis.scores, d).reason.startswith("Simulated") for d in ("skills", "experience", "culture", "career"))
    assert [(m.requirement, m.verified) for m in analysis.matched] == [("NMC registration", True)]
    assert [(m.requirement, m.verified) for m in analysis.missing] == [("IV‑trained", True)]
    assert analysis.risks == ["Salary below your minimum"] and analysis.unclear == ["Hours"]
    assert SimulatedScorer().score(REQUEST) == result  # deterministic


def test_which_scorer_runs():
    assert get_scorer(Settings(anthropic_api_key="")).provider == "simulated"
    assert get_scorer(Settings(anthropic_api_key="sk-test", ai_provider="simulated")).provider == "simulated"
    scorer = get_scorer(Settings(anthropic_api_key="sk-test", ai_model="claude-sonnet-5-5", ai_effort="low"))
    assert (scorer.provider, scorer.model, scorer.effort) == ("anthropic", "claude-sonnet-5-5", "low")
    with pytest.raises(Exception, match="ANTHROPIC_API_KEY"):
        get_scorer(Settings(anthropic_api_key="", ai_provider="anthropic"))
    assert describe(Settings(anthropic_api_key="")) == {"provider": "simulated", "model": "simulated", "effort": ""}
    assert "sk-test" not in str(describe(Settings(anthropic_api_key="sk-test")))
