"""A saved search -> the queries to send to each source. Pure."""

from __future__ import annotations

from collections.abc import Sequence

from app.matching.evaluate import is_remote_place
from app.sources.base import Query

MAX_QUERIES = 40  # per source, per run


def build_queries(terms: Sequence[str], locations: Sequence[str], countries: Sequence[str],
                  include_remote: bool) -> tuple[list[Query], bool]:
    """Every term in every place: (queries, whether some were dropped).

    "Remote", "Remote (UK)" and the like become remote-only queries rather
    than places; with include_remote, a remote-only query is added anyway."""
    places: list[tuple[str, bool]] = []
    for place in locations:
        entry = ("", True) if is_remote_place(place) else (place.strip(), False)
        if entry not in places:
            places.append(entry)
    if not places:
        places.append(("", False))
    if include_remote and ("", True) not in places:
        places.append(("", True))
    queries = []
    for term in dict.fromkeys(t.strip() for t in terms if t.strip()):
        for location, remote in places:
            queries.append(Query(term=term, location=location, countries=tuple(countries), remote=remote))
    return queries[:MAX_QUERIES], len(queries) > MAX_QUERIES
