"""Makes the README's walkthrough GIF and screenshots by driving a running
Job Hunter in a headless browser, so they can be re-made whenever the UI
changes.

Run it against a fresh local stack that uses the built-in sample jobs - real
listings must not end up in the repo (the job boards' terms don't allow
passing them on):

    JOB_SOURCES=demo docker compose up --build      # in .env, or exported
    pip install playwright==1.64.1 pillow==11.3.0
    playwright install chromium
    python3 scripts/readme_media.py                  # writes docs/images/

Without ANTHROPIC_API_KEY the scores come from the simulated scorer, and
the pictures say so; with a key, Claude writes them (about 30 scores, a few
cents with the default model).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, expect, sync_playwright

VIEW = {"width": 1200, "height": 760}


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
    raise SystemExit(f"No sign-in email for {address} reached Mailpit at {mailpit}.")


class Reel:
    """Frames for the GIF: (image, seconds on screen)."""

    def __init__(self, page: Page):
        self.page, self.frames = page, []

    def frame(self, seconds: float, settle: int = 350, top: bool = False) -> None:
        if top:  # each onboarding step from its title
            self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(settle)
        self.frames.append((Image.open(io.BytesIO(self.page.screenshot())).convert("RGB"), seconds))

    def save(self, path: Path, width: int) -> None:
        scaled = [(img.resize((width, round(img.height * width / img.width)), Image.LANCZOS), s) for img, s in self.frames]
        # One palette for every frame keeps colours steady and the file small.
        palette = scaled[0][0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        frames = [img.quantize(palette=palette, dither=Image.Dither.NONE) for img, _ in scaled]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=[round(s * 1000) for _, s in scaled],
                       loop=0, optimize=True, disposal=1)


def scroll_to(page: Page, locator, offset: int = 90) -> None:
    box = locator.bounding_box()
    page.evaluate("y => window.scrollTo(0, y)", page.evaluate("window.scrollY") + box["y"] - offset)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--web", default="http://localhost:3420")
    parser.add_argument("--mailpit", default="http://localhost:8025")
    parser.add_argument("--email", default="sam@example.com", help="a new account (default sam@example.com)")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "docs" / "images"))
    args = parser.parse_args()
    out, web = Path(args.out), args.web.rstrip("/")
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEW, color_scheme="light")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        reel = Reel(page)

        page.goto(f"{web}/signin")
        page.get_by_label("Email").fill(args.email)
        page.get_by_role("button", name="Email me a sign-in link").click()
        page.wait_for_url("**/signin/check-email**")
        page.goto(sign_in_link(args.mailpit, args.email))
        page.wait_for_load_state("networkidle")
        if "/onboarding" not in page.url:
            raise SystemExit(f"{args.email} has already been set up - use a fresh database or another --email.")

        # 1. Onboarding
        page.get_by_role("radio", name=re.compile("^Healthcare")).click()
        page.get_by_role("radio", name=re.compile("^United Kingdom")).click()
        reel.frame(2.2, top=True)
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("checkbox", name=re.compile("Registered nurse")).check()
        custom = page.get_by_label("Other roles, in your own words")
        custom.fill("Research nurse")
        custom.press("Enter")
        page.get_by_role("button", name="Mid level").click()
        page.get_by_role("button", name="Senior", exact=True).click()
        page.get_by_label("Years of experience").fill("4")
        reel.frame(2.2, top=True)
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="+ Manchester").click()
        page.get_by_role("button", name="On-site", exact=True).click()
        page.get_by_role("button", name="Hybrid", exact=True).click()
        page.get_by_label("Where you can work without a visa").select_option("GB")
        page.get_by_label("Minimum salary (optional)").fill("32,000")
        reel.frame(2.2, top=True)
        page.get_by_role("button", name="Continue").click()
        for skill in ("Wound care", "Care planning", "Patient assessment", "Medication administration"):
            page.get_by_role("button", name=f"+ {skill}").click()
        page.get_by_label("Your name").fill("Sam Example")
        page.get_by_role("button", name="Finish").click()
        page.wait_for_url(f"{web}/")

        # 2. The search runs on the worker, then the matches are scored.
        page.get_by_role("link", name="Jobs", exact=True).click()
        page.wait_for_url("**/jobs")
        expect(page.get_by_text("Staff Nurse - Acute Medicine")).to_be_visible(timeout=90_000)
        expect(page.get_by_title("Scoring")).to_have_count(0, timeout=120_000)
        page.reload()
        page.wait_for_load_state("networkidle")
        page.get_by_role("link", name="Best fit").click()
        page.wait_for_url("**sort=fit**")
        page.wait_for_load_state("networkidle")
        reel.frame(3.0)

        job = page.get_by_role("button", name=re.compile("Staff Nurse - Acute Medicine"))
        job.click()
        expect(page.get_by_text("counts 30%")).to_be_visible()
        scroll_to(page, job)
        reel.frame(3.5, settle=800)
        page.mouse.wheel(0, 520)
        reel.frame(3.0)

        page.goto(f"{web}/jobs?view=filtered")
        page.wait_for_load_state("networkidle")
        reel.frame(3.0)
        page.goto(f"{web}/")
        page.wait_for_load_state("networkidle")
        reel.frame(3.0)
        reel.save(out / "walkthrough.gif", width=960)

        # 3. Still pictures, light and dark.
        state = ctx.storage_state()
        for scheme in ("light", "dark"):
            still = browser.new_context(viewport={"width": 1200, "height": 900}, color_scheme=scheme, storage_state=state)
            pg = still.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            suffix = "" if scheme == "light" else "-dark"
            pg.goto(f"{web}/jobs?sort=fit")
            pg.wait_for_load_state("networkidle")
            pg.screenshot(path=out / f"jobs{suffix}.png")
            job = pg.get_by_role("button", name=re.compile("Staff Nurse - Acute Medicine"))
            job.click()
            expect(pg.get_by_text("counts 30%")).to_be_visible()
            pg.wait_for_timeout(600)
            scroll_to(pg, job, offset=72)  # clear of the sticky top bar
            pg.screenshot(path=out / f"job-fit{suffix}.png")
            pg.goto(f"{web}/")
            pg.wait_for_load_state("networkidle")
            pg.screenshot(path=out / f"dashboard{suffix}.png")
            still.close()
        browser.close()

    for png in out.glob("*.png"):  # smaller files, same pixels
        Image.open(png).save(png, optimize=True)
    print("\n".join(f"{f.name}: {f.stat().st_size // 1024} KB" for f in sorted(out.iterdir())))
    if errors:
        raise SystemExit("Errors on the page: " + "; ".join(errors))


if __name__ == "__main__":
    main()
