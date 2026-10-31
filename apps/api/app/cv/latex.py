"""A CV -> LaTeX source for cv.tex. Pure.

All text from the CV goes through `tex()` (or `url()` for link targets), so
it can never be read as a LaTeX command: special characters become their
escaped forms and control characters are dropped.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import quote, unquote

from app.cv.schema import CvContent
from app.presets import LANGUAGE_LEVELS

TEMPLATE = Path(__file__).with_name("cv.tex")
LETTER_COUNTRIES = {"US", "CA"}  # everywhere else prints on A4

_SPECIAL = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
    "^": r"\textasciicircum{}", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}",
}


def tex(text: str) -> str:
    """Plain text -> LaTeX that prints exactly that text."""
    out = []
    for ch in text:
        if ch.isspace():
            out.append(" ")
        elif unicodedata.category(ch)[0] == "C":
            continue
        else:
            out.append(_SPECIAL.get(ch, ch))
    return re.sub(r" {2,}", " ", "".join(out)).strip()


def url(link: str) -> str:
    """A link target for \\href: percent-encoded down to characters that are
    safe in its argument (no backslash, braces, %, # or ~ left unescaped)."""
    encoded = quote(unquote(link), safe=":/?&=+@!$'()*,;-._").replace("~", "%7E")  # quote() never encodes ~
    return encoded.replace("%", r"\%")


def _shown(link: str) -> str:
    """How a link is printed: 'linkedin.com/in/sam' rather than the full URL."""
    return re.sub(r"^https?://(www\.)?", "", link).rstrip("/")


def _dates(start: str, end: str) -> str:
    if start and end:
        return f"{tex(start)} -- {tex(end)}"
    if start:
        return f"{tex(start)} -- Present"
    return tex(end)


def _where(*parts: str) -> str:
    return tex(", ".join(p for p in parts if p))


def body(cv: CvContent) -> str:
    out: list[str] = []
    if cv.name:
        out.append(rf"\cvname{{{tex(cv.name)}}}")
    if cv.headline:
        out.append(rf"\cvheadline{{{tex(cv.headline)}}}")
    contact = [tex(x) for x in (cv.email, cv.phone, cv.location) if x]
    contact += [rf"\href{{{url(link)}}}{{{tex(_shown(link))}}}" for link in cv.links]
    if contact:
        out.append(r"\cvcontact{" + r"\cvsep{}".join(contact) + "}")
    if cv.summary:
        out += [r"\cvsection{Profile}", tex(cv.summary) + r"\par"]
    if cv.experience:
        out.append(r"\cvsection{Experience}")
        for i, job in enumerate(cv.experience):
            if i:
                out.append(r"\cvgap")
            out.append(rf"\cventry{{{tex(job.title)}}}{{{_dates(job.start, job.end)}}}")
            if job.employer or job.location:
                out.append(rf"\cvwhere{{{_where(job.employer, job.location)}}}")
            if job.bullets:
                out += [r"\begin{itemize}", *(rf"\item {tex(b)}" for b in job.bullets), r"\end{itemize}"]
    if cv.education:
        out.append(r"\cvsection{Education}")
        for i, school in enumerate(cv.education):
            if i:
                out.append(r"\cvgap")
            out.append(rf"\cventry{{{tex(school.qualification)}}}{{{_dates(school.start, school.end)}}}")
            if school.institution or school.location:
                out.append(rf"\cvwhere{{{_where(school.institution, school.location)}}}")
            if school.details:
                out.append(rf"{{\small {tex(school.details)}\par}}")
    if cv.skills:
        out += [r"\cvsection{Skills}", ", ".join(tex(s) for s in cv.skills) + r"\par"]
    if cv.languages:
        levels = dict(LANGUAGE_LEVELS)
        shown = [f"{tex(lang.name)} ({tex(levels.get(lang.level, lang.level).lower())})" for lang in cv.languages]
        out += [r"\cvsection{Languages}", ", ".join(shown) + r"\par"]
    return "\n".join(out) if out else r"\mbox{}"


def render(cv: CvContent, country: str = "") -> str:
    """The whole .tex file for this CV; Letter paper in the US and Canada."""
    paper = "letterpaper" if country in LETTER_COUNTRIES else "a4paper"
    template = TEMPLATE.read_text(encoding="utf-8")
    return template.replace("@@PAPER@@", paper, 1).replace("@@BODY@@", body(cv), 1)
