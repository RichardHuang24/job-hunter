"""CVs: the data, the LaTeX it becomes, building PDFs, and the API - with a
stand-in builder unless LuaLaTeX and the fonts are installed."""

from __future__ import annotations

import os
import shutil
import stat

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.cv import service
from app.cv.build import BuildError, Pdf, build_pdf, page_count
from app.cv.latex import body, render, tex, url
from app.cv.schema import CvContent
from app.db.models import Document
from tests.conftest import auth
from tests.test_search import onboard, work

SPECIALS = r"\ { } $ & # ^ _ % ~"
FULL = {
    "name": "Sam Example", "headline": "Registered nurse", "email": "sam@example.com", "phone": "+44 7700 900123",  # Ofcom's range for fiction, not a real number - public-data: ok
    "location": "Manchester", "links": ["https://www.linkedin.com/in/sam-example/"],
    "summary": "Ward nurse. " + SPECIALS,
    "experience": [{"title": "Staff Nurse", "employer": "Contoso Health", "location": "Manchester", "start": "2022",
                    "bullets": ["Led a team of 6", "Cut errors by 30%"]}],
    "education": [{"qualification": "BSc Nursing", "institution": "University of Manchester", "start": "2016", "end": "2019"}],
    "skills": ["Care planning", "C++ & C#"], "languages": [{"name": "English", "level": "native"}],
}


# The data


def test_cv_text_is_cleaned():
    cv = CvContent.model_validate({
        "name": "  Sam\tExample​  ", "summary": "One\nline\r\nonly", "skills": ["", "SQL", "SQL", " Python "],
        "experience": [{"title": "", "bullets": ["x"]}, {"title": "Nurse", "bullets": ["", "Did things"]}],
        "education": [{"qualification": ""}],
    })
    assert cv.name == "Sam Example" and cv.summary == "One line only"
    assert cv.skills == ["SQL", "Python"]
    assert [(e.title, e.bullets) for e in cv.experience] == [("Nurse", ["Did things"])] and cv.education == []


@pytest.mark.parametrize("link", ["javascript:alert(1)", "https://exa mple.com", "ftp://example.com", "https://x.com/{a}"])
def test_only_web_links(link):
    with pytest.raises(ValidationError):
        CvContent(links=[link])


def test_limits():
    with pytest.raises(ValidationError):
        CvContent(experience=[{"title": "x"}] * 16)
    with pytest.raises(ValidationError):
        CvContent(languages=[{"name": "English", "level": "superb"}])


# LaTeX


def test_every_special_character_is_escaped():
    assert tex(SPECIALS) == (r"\textbackslash{} \{ \} \$ \& \# \textasciicircum{} \_ \% \textasciitilde{}")
    assert tex(r"\input{/etc/passwd}") == r"\textbackslash{}input\{/etc/passwd\}"
    assert tex("a\u0000b\x1bc  d\ne") == "abc d e"
    assert tex("Zürich – Ελληνικά") == "Zürich – Ελληνικά"


def test_link_targets_are_safe_in_href():
    target = url("https://example.com/~sam/cv%20page?a=1&b=2#top")
    assert target == r"https://example.com/\%7Esam/cv\%20page?a=1&b=2\%23top"
    assert not set(target) & set("{}~#\\ ") - {"\\"} and all(part.startswith("%") for part in target.split("\\")[1:])


def test_the_body_holds_only_escaped_text():
    out = body(CvContent.model_validate(FULL))
    assert r"\cvname{Sam Example}" in out and r"\cvsection{Experience}" in out
    assert r"\cventry{Staff Nurse}{2022 -- Present}" in out and r"\cvwhere{Contoso Health, Manchester}" in out
    assert r"\item Cut errors by 30\%" in out and r"C++ \& C\#" in out
    assert r"\href{https://www.linkedin.com/in/sam-example/}{linkedin.com/in/sam-example}" in out
    assert "English (native or bilingual)" in out
    assert body(CvContent()) == r"\mbox{}"


def test_paper_size_follows_the_market():
    assert "letterpaper" in render(CvContent(name="x"), "US") and "a4paper" in render(CvContent(name="x"), "GB")
    source = render(CvContent.model_validate(FULL))
    assert "@@" not in source and source.count(r"\begin{document}") == 1


# Building


def _fake_latex(tmp_path, script: str) -> str:
    path = tmp_path / "fake-latex"
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_build_failures_say_why(tmp_path):
    with pytest.raises(BuildError, match="isn't installed"):
        build_pdf("x", Settings(cv_latex=str(tmp_path / "no-such-latex")))
    slow = _fake_latex(tmp_path, "sleep 5\n")
    with pytest.raises(BuildError, match="longer than 0.2 s"):
        build_pdf("x", Settings(cv_latex=slow, cv_timeout_seconds=0.2))
    failing = _fake_latex(tmp_path, 'echo "./cv.tex:3: Undefined control sequence." > cv.log\nexit 1\n')
    with pytest.raises(BuildError, match=r"cv.tex:3: Undefined control sequence"):
        build_pdf("x", Settings(cv_latex=failing))


def test_a_build_is_sealed_off(tmp_path):
    """LaTeX gets the paranoid file settings and no shell, in its own folder."""
    spy = _fake_latex(tmp_path, f'env > {tmp_path}/env.txt\necho "$@" > {tmp_path}/args.txt\npwd > {tmp_path}/cwd.txt\n'
                                'printf "%%PDF-1.7" > cv.pdf\necho "Output written on cv.pdf (2 pages, 9 bytes)." > cv.log\n')
    pdf = build_pdf("source", Settings(cv_latex=spy))
    assert pdf == Pdf(b"%PDF-1.7", 2)
    env = dict(line.split("=", 1) for line in (tmp_path / "env.txt").read_text().splitlines() if "=" in line)
    assert (env["openin_any"], env["openout_any"], env["shell_escape"]) == ("p", "p", "f")
    assert "-no-shell-escape" in (tmp_path / "args.txt").read_text()
    assert "job-hunter-cv-" in (tmp_path / "cwd.txt").read_text()
    assert page_count("Output written on cv.pdf (1 page, 52785 bytes).") == 1


HAS_LATEX = shutil.which("lualatex") is not None and os.environ.get("CV_SKIP_LATEX") != "1"


@pytest.mark.skipif(not HAS_LATEX, reason="LuaLaTeX isn't installed (CI's Docker run builds real PDFs)")
def test_a_real_pdf_with_awkward_text():
    cv = CvContent.model_validate({**FULL, "summary": FULL["summary"] + r" \input{/etc/passwd} \write18{ls} Ελληνικά Русский ✓"})
    pdf = build_pdf(render(cv, "GB"))
    assert pdf.data.startswith(b"%PDF") and pdf.pages == 1


# The API


@pytest.fixture()
def fake_build(monkeypatch):
    built = []

    def build(source, settings=None):
        built.append(source)
        return Pdf(b"%PDF-1.7 stand-in", 1)
    monkeypatch.setattr(service, "build_pdf", build)
    return built


def test_the_cv_starts_from_the_profile(client, sessions, user):
    onboard(client, user, summary="Ward nurse in Manchester.", skills=["Care planning", "Wound care"],
            languages=[{"name": "English", "level": "native"}])
    cv = client.get("/cv", headers=auth(user.id)).json()
    assert not cv["saved"] and cv["documents"] == []
    content = cv["content"]
    assert (content["name"], content["headline"], content["email"]) == ("Alex", "Registered nurse", "alex@example.com")
    assert content["location"] == "Manchester" and content["skills"] == ["Care planning", "Wound care"]
    assert content["summary"] == "Ward nurse in Manchester." and content["languages"] == [{"name": "English", "level": "native"}]


def test_saving_and_building_a_pdf(client, sessions, user, fake_build):
    onboard(client, user)
    saved = client.put("/cv", headers=auth(user.id), json=FULL)
    assert saved.status_code == 200 and saved.json()["saved"] and saved.json()["content"]["name"] == "Sam Example"
    assert client.put("/cv", headers=auth(user.id), json={**FULL, "links": ["javascript:x"]}).status_code == 422

    queued = client.post("/cv/pdf", headers=auth(user.id))
    assert queued.status_code == 202 and queued.json()["status"] == "queued"
    assert queued.json()["filename"] == "CV - Sam Example.pdf"
    assert client.post("/cv/pdf", headers=auth(user.id)).status_code == 409  # one at a time
    doc_id = queued.json()["id"]
    assert client.get(f"/documents/{doc_id}/file", headers=auth(user.id)).status_code == 409  # not ready

    work(sessions)
    doc = client.get(f"/documents/{doc_id}", headers=auth(user.id)).json()
    assert (doc["status"], doc["pages"], doc["size_bytes"], doc["error"]) == ("done", 1, 17, "")
    assert r"\cvname{Sam Example}" in fake_build[0] and "a4paper" in fake_build[0]
    file = client.get(f"/documents/{doc_id}/file", headers=auth(user.id))
    assert file.status_code == 200 and file.content == b"%PDF-1.7 stand-in"
    assert file.headers["content-type"] == "application/pdf"
    assert file.headers["content-disposition"] == "attachment; filename=\"CV - Sam Example.pdf\"; filename*=UTF-8''CV%20-%20Sam%20Example.pdf"
    assert [d["id"] for d in client.get("/cv", headers=auth(user.id)).json()["documents"]] == [doc_id]

    assert client.delete(f"/documents/{doc_id}", headers=auth(user.id)).status_code == 204
    assert client.get(f"/documents/{doc_id}", headers=auth(user.id)).status_code == 404


def test_a_failed_build_says_why(client, sessions, user, monkeypatch):
    def broken(source, settings=None):
        raise BuildError("./cv.tex:9: Missing character")
    monkeypatch.setattr(service, "build_pdf", broken)
    onboard(client, user)
    doc_id = client.post("/cv/pdf", headers=auth(user.id)).json()["id"]
    work(sessions)
    doc = client.get(f"/documents/{doc_id}", headers=auth(user.id)).json()
    assert doc["status"] == "failed" and "Missing character" in doc["error"]
    assert client.post("/cv/pdf", headers=auth(user.id)).status_code == 202  # and you can try again


def test_old_pdfs_are_deleted(client, sessions, user, fake_build, monkeypatch, tmp_path):
    monkeypatch.setenv("CV_FILES_KEPT", "2")
    from app.config import get_settings
    get_settings.cache_clear()
    onboard(client, user)
    ids = []
    for _ in range(3):
        ids.append(client.post("/cv/pdf", headers=auth(user.id)).json()["id"])
        work(sessions)
    kept = [d["id"] for d in client.get("/cv", headers=auth(user.id)).json()["documents"]]
    assert kept == ids[:0:-1]  # the newest two
    files = sorted(p.name for p in (tmp_path / "files").rglob("*.pdf"))
    assert files == sorted(f"{i}.pdf" for i in ids[1:])
    with sessions() as session:
        assert session.query(Document).count() == 2


def test_nobody_sees_another_persons_cv_or_files(client, sessions, user, fake_build):
    from app.db.models import User

    onboard(client, user)
    doc_id = client.post("/cv/pdf", headers=auth(user.id)).json()["id"]
    work(sessions)
    with sessions() as session:
        other = User(email="kim@example.com", name="Kim")
        session.add(other)
        session.commit()
        other_id = other.id
    for method, path in (("GET", f"/documents/{doc_id}"), ("GET", f"/documents/{doc_id}/file"),
                         ("DELETE", f"/documents/{doc_id}")):
        assert client.request(method, path, headers=auth(other_id)).status_code == 404
    assert client.get("/cv", headers=auth(other_id)).json()["documents"] == []
    assert client.get("/cv").status_code == 401
