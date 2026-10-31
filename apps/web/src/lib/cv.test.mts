import { test } from "node:test";
import assert from "node:assert/strict";
import { describeDocument, fileSize, forSaving, linesToBullets, moveItem, sameCv } from "./cv.ts";
import type { CvContent, CvDocument } from "./types.ts";

const cv: CvContent = {
  name: "Sam", headline: "", email: "", phone: "", location: "", links: ["", "https://example.com"], summary: "",
  experience: [
    { title: "Nurse", employer: "", location: "", start: "", end: "", bullets: ["Led a team", " "] },
    { title: "  ", employer: "Somewhere", location: "", start: "", end: "", bullets: [] },
  ],
  education: [{ qualification: "", institution: "Uni", location: "", start: "", end: "", details: "" }],
  skills: ["SQL"], languages: [{ name: "", level: "native" }],
};

test("bullets, one per line", () => {
  assert.deepEqual(linesToBullets("- Led a team\n\n• Cut errors by 30%\n  * Mentored nurses  \n"), ["Led a team", "Cut errors by 30%", "Mentored nurses"]);
  assert.equal(linesToBullets(Array.from({ length: 12 }, (_, i) => `b${i}`).join("\n")).length, 8);
});

test("moving entries", () => {
  assert.deepEqual(moveItem(["a", "b", "c"], 0, 1), ["b", "a", "c"]);
  assert.deepEqual(moveItem(["a", "b", "c"], 0, -1), ["a", "b", "c"]);
  assert.deepEqual(moveItem(["a", "b", "c"], 2, 1), ["a", "b", "c"]);
});

test("blank entries aren't saved, and don't count as changes", () => {
  const saved = forSaving(cv);
  assert.deepEqual(saved.links, ["https://example.com"]);
  assert.deepEqual(saved.experience.map((e) => [e.title, e.bullets]), [["Nurse", ["Led a team"]]]);
  assert.deepEqual(saved.education, []);
  assert.deepEqual(saved.languages, []);
  assert.ok(sameCv(cv, saved));
  assert.ok(!sameCv(cv, { ...saved, name: "Kim" }));
});

test("documents described", () => {
  const doc: CvDocument = { id: "1", kind: "cv", status: "done", filename: "CV.pdf", size_bytes: 53_000, pages: 1, error: "", requested_at: "", finished_at: "" };
  assert.equal(describeDocument(doc), "1 page · 52 KB");
  assert.equal(describeDocument({ ...doc, pages: 2 }), "2 pages · 52 KB");
  assert.equal(describeDocument({ ...doc, status: "queued" }), "Being made...");
  assert.equal(describeDocument({ ...doc, status: "failed", error: "LaTeX failed" }), "Couldn't be made: LaTeX failed");
  assert.equal(fileSize(900), "900 bytes");
  assert.equal(fileSize(3 * 1024 * 1024), "3.0 MB");
});
