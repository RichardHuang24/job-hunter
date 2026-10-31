"""The browser test: a new person goes through Job Hunter in a real browser
(headless Chromium) - sign in by email, set up, see their jobs scored, look
at one, save one, check the settings - and every page is checked for errors
and for fitting a phone screen in light and dark.

Run it against a running stack with the sample jobs (JOB_SOURCES=demo), as
CI does after `docker compose up`:

    pip install -r scripts/requirements-e2e.txt
    python -m playwright install --with-deps --only-shell chromium
    python3 scripts/browser_test.py

It signs in through Mailpit (http://localhost:8025), which catches the
email. Exits 1 on the first failure, with a screenshot in browser-test/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

PAGES = ("/", "/jobs", "/jobs?sort=fit", "/jobs/searches", "/applications", "/cv", "/settings")


def step(label: str) -> None:
    print(f"ok   {label}", flush=True)


def sign_in_link(mailpit: str, address: str) -> str:
    for _ in range(60):
        messages = json.load(urllib.request.urlopen(f"{mailpit}/api/v1/messages?limit=50")).get("messages") or []
        for message in messages:
            if any(to["Address"] == address for to in message["To"]):
                full = json.load(urllib.request.urlopen(f"{mailpit}/api/v1/message/{message['ID']}"))
                link = re.search(r'https?://[^\s"<>]+/api/auth/callback/[\w-]+\?[^\s"<>]+', full["Text"])
                if link:
                    return link.group().replace("&amp;", "&")
        time.sleep(0.5)
    raise AssertionError(f"no sign-in email for {address} reached Mailpit")


def run(page: Page, web: str, mailpit: str, errors: list[str]) -> dict:
    email = f"browser-{uuid.uuid4().hex[:8]}@example.com"
    page.goto(f"{web}/jobs")
    page.wait_for_url("**/signin**")
    step("signed out, a page sends you to sign in")
    page.get_by_label("Email").fill(email)
    page.get_by_role("button", name="Email me a sign-in link").click()
    page.wait_for_url("**/signin/check-email**")
    page.goto(sign_in_link(mailpit, email))
    page.wait_for_url("**/onboarding")
    step("the emailed link signs you in and starts the setup")

    page.get_by_role("radio", name=re.compile("^Healthcare")).click()
    page.get_by_role("radio", name=re.compile("^United Kingdom")).click()
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("checkbox", name=re.compile("Registered nurse")).check()
    custom = page.get_by_label("Other roles, in your own words")
    custom.fill("Research nurse")
    custom.press("Enter")
    page.get_by_role("button", name="Mid level").click()
    page.get_by_role("button", name="Senior", exact=True).click()
    page.get_by_label("Years of experience").fill("4")
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="+ Manchester").click()
    page.get_by_role("button", name="On-site", exact=True).click()
    page.get_by_role("button", name="Hybrid", exact=True).click()
    page.get_by_label("Where you can work without a visa").select_option("GB")
    page.get_by_label("Minimum salary (optional)").fill("32,000")
    page.get_by_role("button", name="Continue").click()
    for skill in ("Wound care", "Care planning", "Patient assessment"):
        page.get_by_role("button", name=f"+ {skill}").click()
    page.get_by_label("Your name").fill("Robin Example")
    page.get_by_role("button", name="Finish").click()
    page.wait_for_url(f"{web}/")
    expect(page.get_by_role("heading", name="Welcome, Robin Example")).to_be_visible()
    step("the four-step setup finishes on the dashboard")

    page.get_by_role("link", name="Jobs", exact=True).click()
    page.wait_for_url("**/jobs")
    expect(page.get_by_text("Staff Nurse - Acute Medicine", exact=True)).to_be_visible(timeout=90_000)
    step("the first search ran in the background and found matches")
    expect(page.get_by_title("Scoring")).to_have_count(0, timeout=120_000)
    page.reload()
    step("and every match was scored")

    job = page.get_by_role("button", name=re.compile("Staff Nurse - Acute Medicine"))
    job.click()
    expect(page.get_by_role("heading", name="Fit")).to_be_visible()
    expect(page.get_by_text(re.compile(r"^counts \d+%$"))).to_have_count(4)  # skills, experience, ways of working, career
    expect(page.get_by_role("heading", name="Against your profile")).to_be_visible()
    step("a job opens with its fit explained and its checks")

    page.get_by_role("button", name="I've applied").click()
    expect(page.get_by_text("Tracked as")).to_be_visible()
    step("a job can be tracked as applied")

    card = page.locator("li").filter(has=job)
    card.get_by_role("button", name="Save").click()
    expect(card.get_by_role("button", name="Unsave")).to_be_visible()
    page.get_by_role("link", name=re.compile("^Saved")).click()
    expect(page.get_by_text("Staff Nurse - Acute Medicine", exact=True)).to_be_visible()
    step("a job can be saved")

    page.get_by_role("link", name=re.compile("^Filtered out")).click()
    expect(page.get_by_text(re.compile("you’re after mid level or senior"))).to_be_visible()
    step("filtered-out jobs say why")

    matches = page.get_by_role("link", name=re.compile("^Matches"))
    matches.click()
    expect(matches).to_have_attribute("aria-current", "page")  # the matches page has loaded
    page.get_by_role("link", name="Best fit").click()
    page.wait_for_url("**sort=fit**")
    page.wait_for_load_state("networkidle")
    jobs = page.locator("li button[aria-expanded]").all_inner_texts()
    badges = [int(m.group(1)) for m in (re.match(r"\s*(\d+)", text) for text in jobs) if m]
    assert len(badges) == len(jobs) > 1 and badges == sorted(badges, reverse=True), jobs
    step("best fit comes first")

    page.goto(f"{web}/jobs/searches")
    expect(page.get_by_text("From your profile")).to_be_visible()
    page.goto(f"{web}/settings")
    expect(page.get_by_role("heading", name="Check a job title")).to_be_visible()
    page.get_by_label("Job title").fill("Senior Staff Nurse - Band 6")
    page.get_by_role("button", name="Check", exact=True).click()
    expect(page.get_by_text("Would be included")).to_be_visible()
    step("the searches and settings pages work")

    page.get_by_role("link", name="Applications", exact=True).click()
    page.wait_for_url("**/applications")
    row = page.locator("li").filter(has_text="Staff Nurse - Acute Medicine")
    expect(row).to_be_visible()
    row.get_by_label("Status of Staff Nurse - Acute Medicine").select_option("interviewing")
    expect(page.get_by_role("link", name=re.compile(r"^Interviewing\s+1"))).to_be_visible()
    row.get_by_role("button", name=re.compile("Staff Nurse - Acute Medicine")).click()
    row.get_by_label("Next step").fill("Panel interview")
    row.get_by_label("When").fill("2030-01-15")
    row.get_by_role("button", name="Save").click()
    expect(row.get_by_text("Next: Panel interview · 15 Jan 2030")).to_be_visible()
    with page.expect_download() as info:
        page.get_by_role("link", name="Export as CSV").click()
    csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
    assert csv_text.startswith("Company,Job title") and "Panel interview" in csv_text, csv_text[:200]
    page.goto(f"{web}/")
    expect(page.get_by_text("Panel interview")).to_be_visible()
    step("applications move through statuses, show their next step, and export as CSV")

    page.get_by_role("link", name="CV", exact=True).click()
    page.wait_for_url("**/cv")
    expect(page.get_by_label("Name", exact=True)).to_have_value("Robin Example")
    page.get_by_role("button", name="+ Add a job").click()
    page.get_by_label("Job title").fill("Staff Nurse")
    page.get_by_label("Employer").fill("Contoso Health")
    page.get_by_label("What you did").fill("Led a team of 6\nCut medication errors by 30%")
    page.get_by_role("button", name="Save and make PDF").click()
    download_link = page.get_by_role("link", name="Download")
    expect(download_link).to_be_visible(timeout=120_000)
    with page.expect_download() as info:
        download_link.click()
    pdf = Path(info.value.path()).read_bytes()
    assert pdf.startswith(b"%PDF") and info.value.suggested_filename == "CV - Robin Example.pdf", info.value.suggested_filename
    step("the CV page saves a CV and makes a PDF that downloads")
    return page.context.storage_state()


def check_layouts(browser, web: str, state: dict, errors: list[str]) -> None:
    for scheme, name, size in (("light", "phone", {"width": 390, "height": 844}),
                               ("dark", "phone", {"width": 390, "height": 844}),
                               ("dark", "desktop", {"width": 1280, "height": 900})):
        context = browser.new_context(viewport=size, color_scheme=scheme, storage_state=state)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(f"{scheme} {name}: {e}"))
        for path in PAGES:
            page.goto(web + path)
            page.wait_for_load_state("networkidle")
            if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
                raise AssertionError(f"{path} is wider than the screen on a {name} ({scheme})")
        context.close()
    step("every page fits a phone and a desktop, light and dark")


def main() -> int:
    parser = argparse.ArgumentParser(description="Job Hunter in a real browser, end to end.")
    parser.add_argument("--web", default="http://localhost:3420")
    parser.add_argument("--mailpit", default="http://localhost:8025")
    parser.add_argument("--shots", default="browser-test", help="where to save a screenshot on failure")
    args = parser.parse_args()
    web = args.web.rstrip("/")
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            state = run(page, web, args.mailpit, errors)
            check_layouts(browser, web, state, errors)
            page.get_by_role("button", name="Sign out").click()
            page.wait_for_url("**/signin**")
            step("signing out goes back to sign in")
            if errors:
                raise AssertionError("errors in the browser: " + " | ".join(errors))
        except Exception as exc:  # noqa: BLE001 - report it, keep a picture, fail
            Path(args.shots).mkdir(exist_ok=True)
            page.screenshot(path=f"{args.shots}/failure.png", full_page=True)
            print(f"FAIL {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}")
            print("\n".join(str(exc).splitlines()[1:12]))
            return 1
        finally:
            browser.close()
    print("\nThe browser test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
