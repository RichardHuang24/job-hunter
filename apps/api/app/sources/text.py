"""Job descriptions arrive as HTML; the app stores and shows plain text, so
no markup from a source ever reaches a page."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCKS = {"p", "div", "section", "article", "header", "footer", "ul", "ol", "table", "tr", "h1", "h2", "h3", "h4",
           "h5", "h6", "blockquote", "pre", "hr"}
_SKIP = {"script", "style", "head", "title", "noscript", "template", "svg"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self.skipping += 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCKS:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in _BLOCKS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    """'<p>Hello&nbsp;<b>world</b></p><ul><li>One</li></ul>' -> 'Hello world\\n\\n- One'"""
    if not markup:
        return ""
    if "<" not in markup:
        return _tidy(html.unescape(markup))
    parser = _Text()
    parser.feed(markup)
    parser.close()
    return _tidy("".join(parser.parts))


def _tidy(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\r", "")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(^|\n)-\n+", r"\1- ", text)  # an <li> whose text starts in a child block
    return text.strip()
