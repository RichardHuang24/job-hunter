#!/usr/bin/env python3
"""Stops personal data and secrets from reaching this public repo.

    python3 scripts/check_public_data.py --staged   # pre-commit: what is about to be committed
    python3 scripts/check_public_data.py --all      # every tracked file (CI runs this)
    python3 scripts/check_public_data.py --push     # pre-push: reads git's ref lines on stdin

It refuses:
  - files that never belong here: .env files, databases, private keys, dumps;
  - email addresses, except placeholders (example.com, noreply addresses);
  - phone numbers;
  - with --push, also commit messages and author emails;
  - anything on your own denylist: names, handles, employers - whatever you
    never want public. One entry per line in ~/.config/job-hunter/denylist.txt
    (or the file JOB_HUNTER_DENYLIST names); lines starting with # are notes.
    Entries match whole words, ignoring case: "Acme" catches "acme's" but
    not "Acmes".
    The denylist stays on your machine, and a match is reported by its line
    number in that file, never by what it says.

A line that must keep a match (a documented example, say) can end with the
comment `public-data: ok`. Standard library only - no install needed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ZERO = "0" * 40
FORBIDDEN_NAMES = {".env", "id_rsa", "id_ecdsa", "id_ed25519", ".npmrc", ".pypirc", ".netrc"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".dump", ".pem", ".key", ".p12", ".pfx", ".kdbx"}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
SAFE_EMAIL = re.compile(
    r"(@(?:[\w-]+\.)*example\.(?:com|org|net)$)|(@[\w.-]+\.(?:example|test|invalid|localhost)$)"
    r"|(@users\.noreply\.github\.com$)|(^noreply@anthropic\.com$)|(^git@github\.com$)",
    re.IGNORECASE,
)
PHONE = re.compile(
    r"(?<![\w/#=+.-])(?:\+\d{1,3}[ .-]?\(?\d{1,4}\)?(?:[ .-]?\d{2,4}){2,4}|0\d{2,4}[ -]\d{3,4}[ -]?\d{3,4}|07\d{9})(?![\w.-])"
)
ALLOW = "public-data: ok"


def git(*args: str, input: str | None = None) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, input=input).stdout


def denylist() -> tuple[list[tuple[int, re.Pattern[str]]], str | None]:
    path = Path(os.environ.get("JOB_HUNTER_DENYLIST") or Path.home() / ".config/job-hunter/denylist.txt")
    if not path.is_file():
        return [], None
    entries = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        entry = line.strip()
        if entry and not entry.startswith("#") and len(entry) >= 3:
            entries.append((number, re.compile(rf"(?<!\w){re.escape(entry)}(?!\w)", re.IGNORECASE)))
    return entries, str(path)


def forbidden_file(path: str) -> str | None:
    p = PurePosixPath(path)
    if p.name in FORBIDDEN_NAMES or (p.name.startswith(".env.") and p.name != ".env.example"):
        return "this kind of file holds secrets and is never committed"
    if p.suffix.lower() in FORBIDDEN_SUFFIXES:
        return f"{p.suffix} files (databases, keys, dumps) are never committed"
    return None


def scan_text(where: str, text: str, deny: list[tuple[int, re.Pattern[str]]]) -> list[str]:
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW in line:
            continue
        for email in EMAIL.findall(line):
            if not SAFE_EMAIL.search(email):
                problems.append(f"{where}:{number}: an email address (use one @example.com)")
        if PHONE.search(line):
            problems.append(f"{where}:{number}: what looks like a phone number")
        for entry_line, entry in deny:
            if entry.search(line):
                problems.append(f"{where}:{number}: matches denylist line {entry_line}")
    return problems


def scan_blob(where: str, data: bytes, deny: list[tuple[int, re.Pattern[str]]]) -> list[str]:
    if b"\0" in data[:8192]:
        return []  # binary
    return scan_text(where, data.decode("utf-8", errors="replace"), deny)


def blob(spec: str) -> bytes:
    return subprocess.run(["git", "show", spec], check=True, capture_output=True).stdout


def check_paths(paths: list[str], read, deny) -> list[str]:
    problems = []
    for path in paths:
        reason = forbidden_file(path)
        if reason:
            problems.append(f"{path}: {reason}")
            continue
        problems += scan_blob(path, read(path), deny)
    return problems


def check_commits(commits: list[str], deny) -> list[str]:
    problems = []
    for sha in commits:
        author, committer = git("show", "-s", "--format=%ae%n%ce", sha).split()
        for email in (author, committer):
            if not SAFE_EMAIL.search(email):
                problems.append(f"commit {sha[:10]}: its author or committer email is a personal address - "
                                "set a GitHub noreply address (git config user.email) and amend")
        problems += scan_text(f"commit {sha[:10]} message", git("show", "-s", "--format=%B", sha), deny)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="the files staged for commit")
    mode.add_argument("--all", action="store_true", help="every tracked file in the working tree")
    mode.add_argument("--push", action="store_true", help="pre-push hook: ref lines on stdin")
    args = parser.parse_args()
    os.chdir(git("rev-parse", "--show-toplevel").strip())

    deny, deny_path = denylist()
    problems: list[str] = []
    if args.staged:
        paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0")
        problems = check_paths([p for p in paths if p], lambda p: blob(f":{p}"), deny)
    elif args.all:
        paths = [p for p in git("ls-files", "-z").split("\0") if p]
        problems = check_paths(paths, lambda p: Path(p).read_bytes() if Path(p).is_file() else b"", deny)
    else:
        for line in sys.stdin.read().splitlines():
            local_ref, local_sha, _remote_ref, remote_sha = line.split()
            if local_sha == ZERO:
                continue  # deleting a branch
            span = [local_sha, "--not", "--remotes"] if remote_sha == ZERO else [f"{remote_sha}..{local_sha}"]
            commits = [c for c in git("rev-list", *span).split() if c]
            paths = [p for p in git("ls-tree", "-r", "--name-only", "-z", local_sha).split("\0") if p]
            problems += check_commits(commits, deny)
            problems += check_paths(paths, lambda p, sha=local_sha: blob(f"{sha}:{p}"), deny)

    if not deny_path:
        print("note: no denylist found (~/.config/job-hunter/denylist.txt) - checked the general patterns only", file=sys.stderr)
    if problems:
        print("Personal data or secrets would be published:", file=sys.stderr)
        for problem in dict.fromkeys(problems):
            print(f"  {problem}", file=sys.stderr)
        print(f"Fix these, or end a line with `{ALLOW}` if it is meant to be public.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
