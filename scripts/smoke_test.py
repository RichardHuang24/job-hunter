#!/usr/bin/env python3
"""Checks a running Job Hunter end to end, the way a person would use it:
signs in by email (reading the link from Mailpit), goes through the setup,
waits for the worker to run the first job search and checks what it found,
checks a few job titles, edits the target roles, checks the API door
refuses what it should, signs out. Needs the worker running.

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
    check("the email form sends a link", status == 303 and headers.get("location", "").endswith("/signin/check-email"), (status, headers.get("location")))
    status, _, page = browser.get(headers["location"])
    check("and shows the check-your-email page", status == 200 and "Check your email" in page, status)

    link = sign_in_link(args.mailpit.rstrip("/"), address)
    status, _, _ = browser.get(link)
    check("the emailed link signs in", status in (302, 303) and any(c.name.endswith("authjs.session-token") for c in browser.cookies), status)
    status, headers, _ = Client(args.web).get(link)
    check("and works only once", "error=Verification" in headers.get("location", ""), (status, headers.get("location")))

    status, headers, _ = browser.get("/")
    check("a new account is sent to the setup", status == 307 and "/onboarding" in headers.get("location", ""), status)
    status, _, page = browser.get("/onboarding")
    check("the setup renders", status == 200 and "what you’re looking for" in page, status)
    status, _, body = browser.get("/api/backend/me")
    check("the API knows who is signed in", status == 200 and json.loads(body)["email"] == address, body)
    status, _, body = browser.get("/api/backend/presets/industries/healthcare")
    check("industry presets come through", status == 200 and any(r["key"] == "registered-nurse" for r in json.loads(body)["roles"]), status)

    setup = {
        "display_name": "Smoke Test", "headline": "Registered nurse", "industry": "healthcare", "market": "uk",
        "roles": ["registered-nurse"], "custom_roles": [{"label": "Research nurse", "titles": ["research nurse"]}],
        "seniority_levels": ["mid", "senior"], "locations": ["Manchester"], "work_arrangements": ["onsite", "hybrid"],
        "authorized_countries": ["GB"], "salary_min": 32000, "salary_currency": "GBP", "skills": ["Wound care"],
    }
    status, _, body = browser.json("POST", "/api/backend/me/onboarding", setup)
    check("the setup saves", status == 200 and [t["label"] for t in json.loads(body)["targets"]] == ["Registered nurse", "Research nurse"], body)
    status, _, page = browser.get("/")
    check("the dashboard shows it", status == 200 and all(text in page for text in (
        "Welcome, Smoke Test", "Research nurse", "Manchester", "£32,000 per year")), status)

    searches = json.loads(browser.get("/api/backend/searches")[2])
    check("the setup made a search and started it", len(searches) == 1 and searches[0]["last_run"]["trigger"] == "onboarding", searches)
    deadline = time.monotonic() + 90
    while searches[0]["last_run"]["status"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(1)
        searches = json.loads(browser.get("/api/backend/searches")[2])
    run = searches[0]["last_run"]
    check("the worker ran the search", run["status"] == "succeeded" and run["counts"].get("new", 0) > 0, run)

    def view(name: str) -> dict:
        return json.loads(browser.get(f"/api/backend/jobs?view={name}")[2])

    matches = view("matches")
    check("matching jobs were found", {"Staff Nurse - Acute Medicine", "Research Nurse"} <= {i["job"]["title"] for i in matches["items"]}, matches["counts"])
    check("a low salary is flagged", "Registered Nurse - Nights" in {i["job"]["title"] for i in view("flagged")["items"]})
    check("a too-senior job is filtered out", "Lead Staff Nurse - Band 7" in {i["job"]["title"] for i in view("filtered")["items"]})
    first = matches["items"][0]
    status, _, body = browser.json("PATCH", f"/api/backend/jobs/{first['id']}", {"state": "saved"})
    check("a job can be saved", status == 200 and [i["id"] for i in view("saved")["items"]] == [first["id"]], body)
    status, _, page = browser.get("/jobs")
    check("the jobs page lists them", status == 200 and "Staff Nurse - Acute Medicine" in page and "Search now" in page, status)
    status, _, page = browser.get("/jobs/searches")
    check("the searches page renders", status == 200 and "From your profile" in page, status)
    status, headers, _ = browser.get("/onboarding")
    check("the setup now leads to settings", status == 307 and "/settings" in headers.get("location", ""), status)

    def title(text: str) -> dict:
        return json.loads(browser.json("POST", "/api/backend/me/title-check", {"title": text})[2])

    nurse = title("Senior Staff Nurse - Band 6")
    check("a matching title is included", nurse["wanted"] and nurse["level"]["key"] == "senior", nurse)
    check("a title for another job is left out", not title("Primary Teacher")["wanted"])
    status, _, body = browser.json("PUT", "/api/backend/me/targets", [{"label": "Staff nurse", "titles": ["staff nurse"]}])
    check("target roles save", status == 200 and json.loads(body)[0]["search"] == ["Staff nurse"], body)
    check("an unknown industry is refused", browser.json("PUT", "/api/backend/me/profile", {"industry": "astrology"})[0] == 422)
    check("an encoded slash can't reach another API path", browser.get("/api/backend/me%2Fprofile")[0] == 404)
    status, _, page = browser.get("/settings")
    check("settings renders the roles and profile", status == 200 and "Staff nurse" in page and "Target roles" in page, status)

    status, _, page = browser.get("/")
    status, headers, _ = browser.submit("/", form_with(page, "Sign out"), {})
    check("signing out goes back to sign-in", status == 303 and "/signin" in headers.get("location", ""), status)
    check("after sign-out the API door is shut again", browser.get("/api/backend/me")[0] == 401)

    print(f"\nAll {passed} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
