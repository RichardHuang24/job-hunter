"""Role-first public entry, real CV PDF, browser isolation and share metadata.

Run against an isolated demo stack before release, or the public demo:
    python scripts/visitor_browser_test.py --web https://jobs.example.com
Only fictional test visitors are created. They are deleted at the end.
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3420")
    parser.add_argument("--out", default="browser-test/visitor")
    args = parser.parse_args()
    origin = args.web.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    errors, contexts, checks = [], [], []
    with sync_playwright() as p:
        launch = {"headless": True}
        if os.environ.get("JOB_HUNTER_BROWSER"):
            launch["executable_path"] = os.environ["JOB_HUNTER_BROWSER"]
        if os.environ.get("JOB_HUNTER_BROWSER_LIB_DIR"):
            launch["env"] = {**os.environ, "LD_LIBRARY_PATH": os.environ["JOB_HUNTER_BROWSER_LIB_DIR"]}
        browser = p.chromium.launch(**launch)

        def page_for_role(title):
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            contexts.append(context)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            assert page.goto(origin).status == 200
            expect(page.get_by_role("heading", name=re.compile("Your next role"))).to_be_visible()
            page.get_by_label("What role are you looking for?").fill(title)
            page.get_by_role("button", name="Start exploring →").click()
            expect(page.get_by_role("heading", name=f"{title} workspace")).to_be_visible(timeout=30_000)
            return page

        try:
            public = browser.new_context()
            page = public.new_page()
            assert page.goto(origin).status == 200
            image = page.locator('meta[property="og:image"]').first.get_attribute("content")
            assert image and image.startswith(origin), image
            response = page.request.get(urljoin(origin, image))
            assert response.ok and response.headers["content-type"].startswith("image/png")
            assert len(response.body()) > 10_000
            assert page.request.post(origin + "/demo/start", form={"job_title": "Data Analyst"}, headers={"Origin": "https://other.example"}).status == 403
            page.screenshot(path=str(out / "public-entry.png"), full_page=True)
            public.close()
            checks += ["Public homepage without authentication", "Public LinkedIn image and metadata", "Cross-origin start rejected"]

            first = page_for_role("Data Analyst")
            me = first.request.get(origin + "/api/backend/me").json()
            assert me["targets"][0]["label"] == "Data Analyst"
            assert not me["profile"]["skills"] and not me["profile"]["summary"]
            initial = first.request.get(origin + "/api/backend/cv").json()
            assert not any(initial["content"].values()) and initial["documents"] == []
            assert first.request.get(origin + "/api/backend/applications").json()["total"] == 0
            first.goto(origin + "/cv")
            expect(first.get_by_label("Name", exact=True)).to_have_value("")
            expect(first.get_by_label("Email", exact=True)).to_have_value("")
            first.screenshot(path=str(out / "blank-cv.png"), full_page=True)
            first.get_by_label("Name", exact=True).fill("Jordan Example")
            first.get_by_label("Email", exact=True).fill("jordan@example.com")
            first.get_by_label("Summary", exact=True).fill("A fictional visitor testing a personal CV.")
            first.get_by_role("button", name="+ Add a job", exact=True).click()
            first.get_by_label("Job title", exact=True).fill("Data Analyst")
            first.get_by_label("Employer", exact=True).fill("Example Research")
            first.get_by_role("button", name="Save and make PDF", exact=True).click()
            download = first.get_by_role("link", name="Download", exact=True)
            expect(download).to_be_visible(timeout=120_000)
            with first.expect_download() as info:
                download.click()
            assert Path(info.value.path()).read_bytes().startswith(b"%PDF")
            assert info.value.suggested_filename == "CV - Jordan Example.pdf"
            cv = first.request.get(origin + "/api/backend/cv").json()
            document = cv["documents"][0]["id"]
            first.reload()
            expect(first.get_by_label("Name", exact=True)).to_have_value("Jordan Example")
            checks += ["Custom role with blank CV and tracker", "User-authored CV saves across reload", "Real PDF generated and downloaded"]

            second = page_for_role("Product Designer")
            other = second.request.get(origin + "/api/backend/me").json()
            assert other["id"] != me["id"]
            assert not any(second.request.get(origin + "/api/backend/cv").json()["content"].values())
            assert second.request.get(origin + f"/api/backend/documents/{document}/file").status == 404
            checks.append("Separate browser contexts isolate profiles, CVs and PDF files")

            unknown = page_for_role("Urban Planner")
            assert unknown.request.get(origin + "/api/backend/me").json()["profile"]["industry"] == "general"
            checks.append("Unlisted title starts a custom workspace")

            for width in [390, 768, 1440]:
                first.set_viewport_size({"width": width, "height": 900})
                first.goto(origin + "/cv")
                assert first.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                if width == 390:
                    first.screenshot(path=str(out / "mobile-cv.png"), full_page=True)
            checks.append("Responsive CV at 390, 768 and 1440px")

            for visitor in [first, second, unknown]:
                assert visitor.request.delete(origin + "/api/backend/me", data={"confirm": "DELETE"}).status == 204
            checks.append("Only the test visitor workspaces deleted")
            assert not errors, errors
            (out / "result.json").write_text(json.dumps({"status": "passed", "origin": origin, "measured_at": datetime.now(timezone.utc).isoformat(), "checks": checks, "browser_errors": errors}, indent=2))
            print(json.dumps({"status": "passed", "checks": checks}))
        finally:
            for context in contexts:
                context.close()
            browser.close()


if __name__ == "__main__":
    main()
