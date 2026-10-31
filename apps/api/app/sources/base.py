"""What every job source (connector) looks like.

A source turns a `Query` into `Posting`s. It declares where it works and on
what terms, so the app can pick sources per search and a hosted deployment
can switch off any whose terms don't allow commercial use. See
docs/job-sources.md for adding one.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


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


class Source(ABC):
    key: ClassVar[str]  # stored with every job: lowercase, no spaces
    label: ClassVar[str]
    description: ClassVar[str]
    homepage: ClassVar[str] = ""
    countries: ClassVar[tuple[str, ...]] = ()  # where it has jobs; () means anywhere
    commercial: ClassVar[bool]  # its terms allow use in a paid, hosted product
    needs_key: ClassVar[str] = ""  # the setting that holds its API key, if it needs one
    demo: ClassVar[bool] = False  # sample data, not real postings

    def covers(self, query: Query) -> bool:
        return not self.countries or not query.countries or bool(set(self.countries) & set(query.countries))

    @abstractmethod
    def search(self, query: Query) -> list[Posting]:
        """Postings for the query. Raise on failure - the search records the
        error against this source and carries on with the others."""
