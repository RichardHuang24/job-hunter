"""What every job source (connector) looks like.

A source turns a `Query` into `Posting`s. It declares where it works and on
what terms, so the app can pick sources per search and a hosted deployment
can switch off any whose terms don't allow commercial use. See
docs/job-sources.md for adding one.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Literal

from app.matching.titles import normalize, spans

Status = Literal["open", "closed", "unknown"]


def title_has_words(title: str, phrase: str) -> bool:
    """Every word of the search term is in the title, as a whole word - how
    job boards match a title search."""
    text = normalize(title)
    return all(spans(word, text) for word in normalize(phrase).split())


@dataclass(frozen=True)
class Query:
    term: str  # what to search for: "staff nurse"
    location: str = ""  # a place, or "" for anywhere in `countries`
    countries: tuple[str, ...] = ()  # ISO 3166-1 alpha-2 codes; () means anywhere
    remote: bool = False  # only remote jobs
    limit: int = 50


@dataclass(frozen=True)
class Posting:
    source_id: str  # the source's own id - stable across searches
    url: str
    title: str
    company: str = ""
    location: str = ""  # as the source writes it: "Salford, Greater Manchester"
    country: str = ""  # ISO code; "" when not stated
    arrangement: str = ""  # onsite / hybrid / remote; "" when not stated
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = ""  # ISO 4217
    salary_period: str = ""  # year / month / day / hour
    posted_at: dt.datetime | None = None
    description: str = ""  # plain text
    # Remote jobs: where candidates may live. () with worldwide=False: not stated.
    countries: tuple[str, ...] = ()  # ISO codes
    worldwide: bool = False
    expires_at: dt.datetime | None = None  # the source takes it down by then, if not sooner


class Source(ABC):
    key: ClassVar[str]  # stored with every job: lowercase, no spaces
    label: ClassVar[str]
    description: ClassVar[str]
    homepage: ClassVar[str] = ""
    countries: ClassVar[tuple[str, ...]] = ()  # where it has jobs; () means anywhere
    commercial: ClassVar[bool]  # its terms allow use in a paid, hosted product
    needs_key: ClassVar[str] = ""  # the setting that holds its API key, if it needs one
    demo: ClassVar[bool] = False  # sample data, not real postings
    remote_only: ClassVar[bool] = False  # only remote jobs: asked only for remote searches
    # Sources whose terms say to take down closed jobs: how often to check a
    # stored job is still open, and how many to check per pass (see check()).
    check_every: ClassVar[dt.timedelta | None] = None
    check_batch: ClassVar[int] = 100

    def covers(self, query: Query) -> bool:
        if self.remote_only and not query.remote:
            return False
        return not self.countries or not query.countries or bool(set(self.countries) & set(query.countries))

    def check(self, jobs: Sequence[tuple[str, str]]) -> dict[str, Status]:
        """Whether stored jobs are still open: (source_id, url) pairs ->
        source_id -> status. Only sources with check_every need this."""
        return {}

    @abstractmethod
    def search(self, query: Query) -> list[Posting]:
        """Postings for the query. Raise on failure - the search records the
        error against this source and carries on with the others."""
