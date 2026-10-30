"""A job title -> which of a person's target roles it is, and how senior.

    match_title("Senior Staff Nurse (Band 6)", targets, levels)
    -> the "Registered nurse" target, matched on "staff nurse", level "senior"

Titles and phrases are compared normalised: lowercase, with punctuation as
spaces, so "Front-End Developer" and "front end developer" are the same, and
phrases match whole words only ("nurse" doesn't match "nursery").

The target is the one with the longest matching phrase; a target whose
exclude phrases appear is skipped. The level is the highest level whose words
appear, with two exceptions that keep role names from being read as levels:
a word inside a longer level phrase doesn't count ("head of" inside "head of
year"), and nor does one inside the matched role phrase ("manager" in
"product manager"). No level words: "mid".
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

_SEPARATORS = re.compile(r"[^\w&+#]+|_")
DEFAULT_LEVEL = "mid"


def normalize(text: str) -> str:
    """'Front-End Developer (UK)' -> 'front end developer uk'"""
    return _SEPARATORS.sub(" ", (text or "").casefold()).strip()


def spans(phrase: str, text: str) -> list[tuple[int, int]]:
    """Where a normalised phrase appears in normalised text, as whole words."""
    if not phrase:
        return []
    return [m.span() for m in re.finditer(rf"(?<!\S){re.escape(phrase)}(?!\S)", text)]


class TargetLike(Protocol):
    @property
    def label(self) -> str: ...
    @property
    def titles(self) -> Sequence[str]: ...
    @property
    def exclude(self) -> Sequence[str]: ...


class LevelLike(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def words(self) -> Sequence[str]: ...


@dataclass(frozen=True)
class TitleMatch:
    target: TargetLike | None
    phrase: str  # the target phrase that matched; "" when no target did
    level: str  # a level key
    level_words: tuple[str, ...]  # the words that set the level; () for the default


def _inside(inner: tuple[int, int], outer: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def best_target(title: str, targets: Sequence[TargetLike]) -> tuple[TargetLike, str, tuple[int, int]] | None:
    """The target with the longest phrase in the (normalised) title; ties go to the earlier target."""
    best = None
    for index, target in enumerate(targets):
        if any(spans(normalize(p), title) for p in target.exclude):
            continue
        for phrase in target.titles:
            phrase = normalize(phrase)
            for span in spans(phrase, title):
                rank = (len(phrase), -index)
                if best is None or rank > best[0]:
                    best = (rank, target, phrase, span)
    return None if best is None else best[1:]


def seniority(title: str, levels: Sequence[LevelLike], role_span: tuple[int, int] | None = None) -> tuple[str, tuple[str, ...]]:
    """(level key, the words that set it) for a normalised title."""
    found = [(span, rank, word) for rank, level in enumerate(levels) for word in level.words
             for span in spans(normalize(word), title)]
    kept = [
        (span, rank, word) for span, rank, word in found
        if not any(_inside(span, other) and span != other for other, _, _ in found)
        and not (role_span and _inside(span, role_span))
    ]
    if not kept:
        return DEFAULT_LEVEL, ()
    top = max(rank for _, rank, _ in kept)
    return levels[top].key, tuple(dict.fromkeys(word for _, rank, word in kept if rank == top))


def match_title(title: str, targets: Sequence[TargetLike], levels: Sequence[LevelLike]) -> TitleMatch:
    text = normalize(title)
    found = best_target(text, targets)
    if found is None:
        level, words = seniority(text, levels)
        return TitleMatch(None, "", level, words)
    target, phrase, span = found
    level, words = seniority(text, levels, span)
    return TitleMatch(target, phrase, level, words)
