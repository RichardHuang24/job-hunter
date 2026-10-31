"""Who does the scoring: Claude through the Anthropic API, or - when no API
key is set - a simulated scorer that runs locally, costs nothing, and says
in every reason that it's simulated.

AI_PROVIDER picks: "auto" (Claude when ANTHROPIC_API_KEY is set, otherwise
simulated), "anthropic" or "simulated".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

import anthropic
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.matching.titles import normalize, spans
from app.scoring.prompt import Analysis, Matched, Missing, answer_schema, check_evidence, parse_answer

log = logging.getLogger("job_hunter.scoring")

MAX_TOKENS = 16_000  # thinking and the JSON share it; only what's used is billed
# Models the API can re-run on another model server-side when they decline a request.
SERVER_FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-fable-5", "claude-sonnet-5-5"})
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# USD per million tokens (input, output), Anthropic's list prices as of
# October 2026. Cache reads cost 0.1x input, 5-minute cache writes 1.25x.
# Override with AI_PRICE_INPUT / AI_PRICE_OUTPUT for a model not listed.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-fable-5-1": (10.00, 50.00),
}
HAIKU_LONG_PROMPT = 100_000  # Haiku 5.5 costs more above this many prompt tokens
HAIKU_LONG_PRICES = (0.50, 2.50)


@dataclass(frozen=True)
class ScoreRequest:
    system: str  # instructions and the person's profile - cached between calls
    message: str  # the posting and its checks
    posting: str  # the posting's own text, to check quotes against
    skills: tuple[str, ...] = ()  # for the simulated scorer
    role: str = ""  # the target role it counts as; "" for none
    level_wanted: bool | None = None  # None: the person wants any level
    arrangement_fits: bool | None = None  # None: the posting doesn't say
    field_skills: tuple[str, ...] = ()  # the industry's usual skills
    flags: tuple[str, ...] = ()  # deal-breaker checks that flagged something
    unknowns: tuple[str, ...] = ()  # deal-breaker checks the posting didn't settle


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @classmethod
    def of(cls, usage: Any) -> Usage:
        def get(name: str) -> int:
            return int(getattr(usage, name, 0) or 0)
        return cls(get("input_tokens"), get("output_tokens"), get("cache_read_input_tokens"), get("cache_creation_input_tokens"))

    def __add__(self, other: Usage) -> Usage:
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens,
                     self.cache_read_tokens + other.cache_read_tokens, self.cache_write_tokens + other.cache_write_tokens)


@dataclass
class ScoreResult:
    analysis: Analysis
    provider: str  # "anthropic" or "simulated"
    model: str  # the model that answered ("simulated" for the simulator)
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0


class ScoringError(RuntimeError):
    """A score that couldn't be made. `stop` means the rest of the batch
    would fail the same way (a bad key, rate limits, the API unreachable)."""

    def __init__(self, code: str, message: str, *, stop: bool = False):
        super().__init__(message)
        self.code, self.stop = code, stop


class Scorer(Protocol):
    provider: str
    model: str

    def score(self, request: ScoreRequest) -> ScoreResult: ...


def estimate_cost(model: str, usage: Usage, settings: Settings | None = None) -> float:
    """USD for one response's usage; 0 for a model with no known price."""
    settings = settings or get_settings()
    prompt = usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
    if settings.ai_price_input or settings.ai_price_output:
        price_in, price_out = settings.ai_price_input, settings.ai_price_output
    elif model == "claude-haiku-5-5" and prompt > HAIKU_LONG_PROMPT:
        price_in, price_out = HAIKU_LONG_PRICES
    elif model in PRICES:
        price_in, price_out = PRICES[model]
    else:
        log.warning("No price known for %s - recording its cost as 0", model)
        return 0.0
    cost = (usage.input_tokens * price_in + usage.cache_read_tokens * price_in * 0.1
            + usage.cache_write_tokens * price_in * 1.25 + usage.output_tokens * price_out)
    return round(cost / 1_000_000, 6)


def usage_parts(response: Any) -> list[tuple[str, Usage]]:
    """(model, usage) per attempt. With a server-side fallback, usage.iterations
    lists every attempt and the top-level usage only the last one."""
    usage = getattr(response, "usage", None)
    iterations = getattr(usage, "iterations", None) or []
    if iterations:
        return [(getattr(it, "model", None) or response.model, Usage.of(it)) for it in iterations]
    return [(response.model, Usage.of(usage))]


def parse_response(response: Any, posting: str) -> Analysis:
    """The analysis from a response, by content-block type (thinking blocks
    come first). Raises ScoringError on a refusal, a cut-off answer or JSON
    that doesn't fit the schema."""
    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise ScoringError("refusal", "Claude declined to score this posting" + (f" ({category})." if category else "."))
    if stop == "max_tokens":
        raise ScoringError("cut_off", "The answer was cut off before it finished.")
    text = next((block.text for block in response.content if getattr(block, "type", None) == "text"), None)
    if not text:
        raise ScoringError("empty", "Claude returned no answer.")
    try:
        return check_evidence(parse_answer(text), posting)
    except (ValueError, ValidationError) as exc:
        raise ScoringError("invalid", f"The answer didn't fit the expected shape: {str(exc)[:200]}") from exc


class AnthropicScorer:
    provider = "anthropic"

    def __init__(self, client: Any, model: str, effort: str, settings: Settings | None = None):
        self.client, self.model, self.effort = client, model, effort
        self.settings = settings or get_settings()

    def params(self, request: ScoreRequest) -> dict[str, Any]:
        """The request. No sampling parameters (current models reject them);
        thinking is left at each model's default (adaptive)."""
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": [{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": request.message}],
            "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": answer_schema()}},
        }

    def _send(self, params: dict[str, Any]) -> Any:
        if self.model in SERVER_FALLBACK_MODELS:
            # If the model declines for safety reasons, the API re-runs the
            # request on the model Anthropic recommends, within the same call.
            return self.client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
        return self.client.messages.create(**params)

    def score(self, request: ScoreRequest) -> ScoreResult:
        try:
            response = self._send(self.params(request))
        except anthropic.AuthenticationError as exc:
            raise ScoringError("auth", "The Anthropic API key was rejected - check ANTHROPIC_API_KEY.", stop=True) from exc
        except anthropic.PermissionDeniedError as exc:
            raise ScoringError("permission", f"The API key can't use {self.model}.", stop=True) from exc
        except anthropic.RateLimitError as exc:
            raise ScoringError("rate_limited", "Claude is rate-limiting this key - scores will resume later.", stop=True) from exc
        except anthropic.BadRequestError as exc:
            raise ScoringError("bad_request", f"Claude rejected the request: {exc.message}"[:300]) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ScoringError("unavailable", "Claude is unavailable right now - try again later.", stop=True) from exc
            raise ScoringError("api_error", f"The Anthropic API answered {exc.status_code}: {exc.message}"[:300],
                               stop=exc.status_code == 402) from exc
        except anthropic.APIConnectionError as exc:  # timeouts included
            raise ScoringError("unreachable", "Couldn't reach the Anthropic API.", stop=True) from exc
        analysis = parse_response(response, request.posting)
        parts = usage_parts(response)
        usage = sum((u for _, u in parts), Usage())
        cost = round(sum(estimate_cost(model, u, self.settings) for model, u in parts), 6)
        return ScoreResult(analysis, self.provider, getattr(response, "model", self.model), usage, cost)


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return sentence[:200]


class SimulatedScorer:
    """No API key: a quick, free, deterministic stand-in so every screen works.
    It only counts skills and reads the deal-breaker checks - it understands
    nothing - and every reason says so."""

    provider = "simulated"
    model = "simulated"

    def score(self, request: ScoreRequest) -> ScoreResult:
        posting = request.posting
        text = normalize(posting)
        found = [s for s in request.skills if spans(normalize(s), text)]
        mine = {normalize(s) for s in request.skills}
        gaps = [s for s in request.field_skills if normalize(s) not in mine and spans(normalize(s), text)]

        def quote(skill: str) -> str:
            """The posting's own wording of a skill - any punctuation between its words."""
            words = [re.escape(w) for w in re.findall(r"\w+", skill)]
            match = re.search(r"(?<!\w)" + r"[\W_]+".join(words) + r"(?!\w)", posting, re.IGNORECASE) if words else None
            return match.group() if match else skill

        n = len(request.skills)
        skills = 50 if not n else min(95, 40 + round(55 * len(found) / n))
        experience = {None: 70, True: 80, False: 45}[request.level_wanted]
        culture = {None: 62, True: 74, False: 50}[request.arrangement_fits]
        career = 78 if request.role else 35
        level_note = {None: "you're open to any level", True: "it's a level you want", False: "it isn't a level you want"}
        arrangement_note = {None: "the posting doesn't say how the work is arranged",
                            True: "its work arrangement suits you", False: "its work arrangement doesn't suit you"}
        analysis = Analysis.model_validate({
            "summary": _first_sentence(posting.split("\n", 1)[-1] if "\n" in posting else posting) or "No description.",
            "scores": {
                "skills": {"score": skills, "reason": f"Simulated: {len(found)} of your {n} listed skills appear in the posting." if n
                           else "Simulated: add skills to your profile to score this."},
                "experience": {"score": experience, "reason": f"Simulated: based only on level - {level_note[request.level_wanted]}."},
                "culture": {"score": culture, "reason": f"Simulated: based only on whether {arrangement_note[request.arrangement_fits]}."},
                "career": {"score": career, "reason": f"Simulated: it counts as your {request.role} role." if request.role
                           else "Simulated: it isn't one of your target roles."},
            },
            "matched": [{"requirement": quote(s), "detail": "In your skills"} for s in found[:8]],
            "missing": [{"requirement": quote(s), "kind": "nice_to_have", "note": "Not in your skills"} for s in gaps[:8]],
            "risks": list(request.flags[:5]),
            "unclear": list(request.unknowns[:5]),
        })
        return ScoreResult(check_evidence(analysis, posting), self.provider, self.model)


class NotConfigured(RuntimeError):
    pass


@lru_cache
def _client(api_key: str, timeout: float) -> anthropic.Anthropic:
    # The key is passed explicitly so a server never falls back to whatever
    # credentials happen to be on the machine.
    return anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)


def get_scorer(settings: Settings | None = None) -> Scorer:
    settings = settings or get_settings()
    choice = settings.ai_provider
    if choice == "simulated" or (choice == "auto" and not settings.anthropic_api_key):
        return SimulatedScorer()
    if not settings.anthropic_api_key:
        raise NotConfigured("AI_PROVIDER is anthropic but ANTHROPIC_API_KEY isn't set.")
    return AnthropicScorer(_client(settings.anthropic_api_key, settings.ai_timeout_seconds), settings.ai_model,
                           settings.ai_effort, settings)


def describe(settings: Settings | None = None) -> dict[str, str]:
    """Which scorer this deployment uses, without the key."""
    settings = settings or get_settings()
    simulated = settings.ai_provider == "simulated" or not settings.anthropic_api_key
    return {"provider": "simulated" if simulated else "anthropic", "model": "simulated" if simulated else settings.ai_model,
            "effort": "" if simulated else settings.ai_effort}


__all__: Sequence[str] = [
    "AnthropicScorer", "Matched", "Missing", "NotConfigured", "ScoreRequest", "ScoreResult", "Scorer", "ScoringError",
    "SimulatedScorer", "Usage", "describe", "estimate_cost", "get_scorer", "parse_response", "usage_parts",
]
