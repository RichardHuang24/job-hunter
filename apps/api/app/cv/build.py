"""LaTeX source -> PDF, with LuaLaTeX, in a throwaway folder.

The source only ever holds escaped text (app/cv/latex.py), and LaTeX runs
with the doors shut anyway: no shell commands, writing only in its own
folder, no reading hidden files, and a time limit.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings


class BuildError(RuntimeError):
    """LaTeX failed. The message holds the useful lines of its log."""


@dataclass(frozen=True)
class Pdf:
    data: bytes
    pages: int


def page_count(log: str) -> int:
    """From LaTeX's own summary: "Output written on cv.pdf (2 pages, 52785 bytes)." """
    found = re.search(r"Output written on \S+ \((\d+) pages?", log)
    return int(found.group(1)) if found else 0


_ERROR = re.compile(r"^(!|\S+\.(tex|sty|cls):\d+: )")


def _log_errors(log: str) -> str:
    """The error lines of a LaTeX log ("./cv.tex:12: Undefined control sequence.")."""
    lines = [line.strip() for line in log.splitlines() if _ERROR.match(line)]
    return " | ".join(dict.fromkeys(lines))[:600] if lines else "LaTeX failed: " + log.strip()[-300:]


def build_pdf(source: str, settings: Settings | None = None) -> Pdf:
    settings = settings or get_settings()
    with tempfile.TemporaryDirectory(prefix="job-hunter-cv-") as folder:
        work = Path(folder)
        (work / "cv.tex").write_text(source, encoding="utf-8")
        env = {
            **os.environ,
            # Reading: no hidden files. Not "p" (paranoid): luaotfload 3.28-3.29, in
            # TeX Live 2024-2025 as Debian ships it, can't load its own data with it.
            "openin_any": "r",
            "openout_any": "p",  # writing: only below this folder
            "shell_escape": "f",
            "TEXMFOUTPUT": str(work),
        }
        command = [settings.cv_latex, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
                   "-file-line-error", "cv.tex"]
        try:
            result = subprocess.run(command, cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=settings.cv_timeout_seconds, check=False)
        except FileNotFoundError as exc:
            raise BuildError(f"{settings.cv_latex} isn't installed here - CV PDFs are built in the Docker image") from exc
        except subprocess.TimeoutExpired as exc:
            raise BuildError(f"LaTeX took longer than {settings.cv_timeout_seconds:g} s") from exc
        pdf, log_file = work / "cv.pdf", work / "cv.log"
        log = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else ""
        if result.returncode != 0 or not pdf.exists():
            raise BuildError(_log_errors(log or result.stdout.decode(errors="replace")))
        return Pdf(pdf.read_bytes(), page_count(log))
