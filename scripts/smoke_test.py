#!/usr/bin/env python3
"""Checks a running Job Hunter end to end, the way a person would use it:
signs in by email (reading the link from Mailpit), opens the dashboard,
saves a profile, checks the API door refuses what it should, signs out.

    docker compose up --build -d
    python3 scripts/smoke_test.py            # defaults suit docker-compose.yml

The forms are posted the way a browser without JavaScript posts them, so
the sign-in and sign-out server actions are exercised too. Each run signs in
a new user (smoke-<random>@example.com). Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from html.parser import HTMLParser
from http.cookiejar import CookieJar


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies), _NoRedirect)

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None):
        """(status, lower-cased headers, text) - redirects are returned, not followed."""
        url = path if path.startswith("http") else self.base + path
        req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with self.opener.open(req, timeout=30) as response:
                return response.status, {k.lower(): v for k, v in response.headers.items()}, _text(response.read())
        except urllib.error.HTTPError as error:
            return error.code, {k.lower(): v for k, v in error.headers.items()}, _text(error.read())

    def get(self, path: str):
        return self.request("GET", path)

    def json(self, method: str, path: str, payload: dict):
        return self.request(method, path, json.dumps(payload).encode(), {"content-type": "application/json"})

    def submit(self, path: str, form: dict, fields: dict[str, str]):
        """Posts a server-action form as a browser without JavaScript does."""
        boundary = uuid.uuid4().hex
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
                 for name, value in {**form["fields"], **fields}.items()]
        body = ("".join(parts) + f"--{boundary}--\r\n").encode()
        headers = {"content-type": f"multipart/form-data; boundary={boundary}", "origin": self.base}
        return self.request("POST", path, body, headers)


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("<!-- -->", "")  # React's text-node markers


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms: list[dict] = []
        self.inside = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append({"fields": {}, "text": ""})
            self.inside = True
        elif tag == "input" and self.inside and attrs.get("type") == "hidden" and attrs.get("name"):
            self.forms[-1]["fields"][attrs["name"]] = attrs.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.forms[-1]["text"] += data


def form_with(page: str, text: str) -> dict:
    parser = _Forms()
    parser.feed(page)
    for form in parser.forms:
        if text in form["text"]:
            return form
    raise AssertionError(f"no form with {text!r} on the page")


def sign_in_link(mailpit: str, address: str, timeout: float = 30) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with urllib.request.urlopen(f"{mailpit}/api/v1/messages?limit=50", timeout=10) as response:
            messages = json.load(response).get("messages") or []
        for message in messages:
            if any(to.get("Address", "").lower() == address for to in message.get("To") or []):
                with urllib.request.urlopen(f"{mailpit}/api/v1/message/{message['ID']}", timeout=10) as response:
                    full = json.load(response)
                found = re.search(r'https?://[^\s"<>]+/api/auth/callback/[\w-]+\?[^\s"<>]+', full.get("Text", "") + full.get("HTML", ""))
                if found:
                    return html.unescape(found.group())
        time.sleep(0.5)
    raise AssertionError(f"no sign-in email for {address} in Mailpit after {timeout:g} s")


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end check of a running Job Hunter.")
    parser.add_argument("--web", default="http://localhost:3420")
    parser.add_argument("--mailpit", default="http://localhost:8025")
    args = parser.parse_args()
    address = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
    browser = Client(args.web)
    passed = 0

    def check(label: str, ok: bool, detail: object = "") -> None:
        nonlocal passed
        if not ok:
            print(f"FAIL {label}" + (f"\n     {detail}" if detail else ""))
            sys.exit(1)
        passed += 1
        print(f"ok   {label}")

    status, headers, _ = browser.get("/")
    check("signed out, pages redirect to sign-in", status == 307 and "/signin" in headers.get("location", ""), status)
    check("signed out, the API door is shut", browser.get("/api/backend/me")[0] == 401)
    check("signed out, the app icon still loads", browser.get("/icon.svg")[0] == 200)

    status, _, page = browser.get("/signin")
    check("the sign-in page renders", status == 200 and "Sign in" in page, status)
    status, headers, _ = browser.submit("/signin", form_with(page, "sign-in link"), {"email": address})
    check("the email form sends a link", status == 303 and "verify-request" in headers.get("location", ""), (status, headers.get("location")))
    status, headers, _ = browser.get(headers["location"])
    check("and shows the check-your-email page", status in (302, 303) and "/signin/check-email" in headers.get("location", ""), status)

    link = sign_in_link(args.mailpit.rstrip("/"), address)
    status, _, _ = browser.get(link)
    check("the emailed link signs in", status in (302, 303) and any(c.name.endswith("authjs.session-token") for c in browser.cookies), status)
    status, headers, _ = Client(args.web).get(link)
    check("and works only once", "error=Verification" in headers.get("location", ""), (status, headers.get("location")))

    status, _, page = browser.get("/")
    check("the dashboard renders", status == 200 and "Welcome" in page, status)
    status, _, body = browser.get("/api/backend/me")
    check("the API knows who is signed in", status == 200 and json.loads(body)["email"] == address, body)
    status, _, body = browser.get("/api/backend/presets")
    check("presets come through", status == 200 and json.loads(body)["industries"], body)

    profile = {"display_name": "Smoke Test", "headline": "Registered nurse", "industry": "healthcare", "market": "uk"}
    status, _, body = browser.json("PUT", "/api/backend/me/profile", profile)
    check("the profile saves", status == 200 and json.loads(body)["industry"] == "healthcare", body)
    status, _, page = browser.get("/")
    check("the dashboard shows it", "Welcome, Smoke Test" in page and "Healthcare" in page and "United Kingdom" in page)
    check("an unknown industry is refused", browser.json("PUT", "/api/backend/me/profile", {"industry": "astrology"})[0] == 422)
    check("an encoded slash can't reach another API path", browser.get("/api/backend/me%2Fprofile")[0] == 404)
    status, _, page = browser.get("/settings")
    check("settings renders the saved profile", status == 200 and "Registered nurse" in page, status)

    status, _, page = browser.get("/")
    status, headers, _ = browser.submit("/", form_with(page, "Sign out"), {})
    check("signing out goes back to sign-in", status == 303 and "/signin" in headers.get("location", ""), status)
    check("after sign-out the API door is shut again", browser.get("/api/backend/me")[0] == 401)

    print(f"\nAll {passed} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
