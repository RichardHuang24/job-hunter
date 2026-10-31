"""Job sources: the registry, and which ones this deployment uses.

JOB_SOURCES lists the sources to use (comma-separated keys; default "demo"):
demo, himalayas, jobicy. A source that needs an API key is skipped until its
key is set, and with COMMERCIAL_ONLY=true so is any whose terms don't allow
commercial use.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.sources.base import Posting, Query, Source
from app.sources.demo import DemoSource
from app.sources.himalayas import HimalayasSource
from app.sources.jobicy import JobicySource

SOURCES: dict[str, type[Source]] = {source.key: source for source in (DemoSource, HimalayasSource, JobicySource)}


def enabled_sources(settings: Settings | None = None) -> list[Source]:
    settings = settings or get_settings()
    out = []
    for key in (k.strip() for k in settings.job_sources.split(",")):
        source = SOURCES.get(key)
        if source is None:
            continue
        if source.needs_key and not getattr(settings, source.needs_key, ""):
            continue
        if settings.commercial_only and not source.commercial:
            continue
        out.append(source())
    return out


__all__ = ["SOURCES", "Posting", "Query", "Source", "enabled_sources"]
