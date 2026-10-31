"""Settings, from the environment (and .env in development).

Nothing secret has a default: BACKEND_JWT_SECRET must be set, or the API
refuses to start - see app/auth.py.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # development | test | production
    database_url: str = "postgresql+psycopg://jobhunter:jobhunter@localhost:5432/jobhunter"

    # The web app signs a short-lived token for each request it forwards to the
    # API (apps/web/src/lib/backend.ts); the API only accepts requests that
    # carry one. Shared secret, at least 32 characters.
    backend_jwt_secret: str = ""
    jwt_issuer: str = "job-hunter-web"
    jwt_audience: str = "job-hunter-api"

    # Worker: how long to sleep when the queue is empty, and how long a claimed
    # task may run before another worker may take it over.
    worker_poll_seconds: float = 1.0
    task_lease_seconds: int = 600

    # Job sources (app/sources): which to use, comma-separated. A hosted,
    # paid deployment sets COMMERCIAL_ONLY so sources whose terms don't allow
    # commercial use stay off.
    job_sources: str = "demo"
    commercial_only: bool = False

    # How often the worker looks for saved searches due to run (seconds).
    schedule_seconds: float = 60.0

    # AI scoring (app/scoring, docs/ai-scoring.md). With no ANTHROPIC_API_KEY,
    # "auto" uses the simulated scorer: free, local, and labelled as such.
    anthropic_api_key: str = ""
    ai_provider: str = "auto"  # auto | anthropic | simulated
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "medium"  # low | medium | high | xhigh | max
    ai_timeout_seconds: float = 120.0
    ai_auto_score: bool = True  # score new matches and flagged jobs after each search
    ai_scores_per_month: int = 300  # per user
    ai_budget_usd_per_month: float = 5.0  # per user
    ai_price_input: float = 0.0  # USD per million tokens, for a model not in app/scoring/providers.py
    ai_price_output: float = 0.0

    # Where the industry and market presets are. Empty: the presets/ folder
    # found above the code (the repo's, or /app/presets in Docker).
    presets_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
