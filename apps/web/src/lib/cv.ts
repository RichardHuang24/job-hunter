// The CV editor's small pure helpers (app/cv/CvEditor.tsx).
import type { CvContent, CvDocument, Education, Experience } from "./types";

export const MAX_BULLETS = 8;

export const emptyExperience = (): Experience => ({ title: "", employer: "", location: "", start: "", end: "", bullets: [] });
export const emptyEducation = (): Education => ({ qualification: "", institution: "", location: "", start: "", end: "", details: "" });

/** The bullets box: one achievement per line. */
export function linesToBullets(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^\s*[-•*]\s*/, "").trim())
    .filter(Boolean)
    .slice(0, MAX_BULLETS);
}

export function moveItem<T>(items: T[], index: number, by: -1 | 1): T[] {
  const to = index + by;
  if (to < 0 || to >= items.length) return items;
  const next = [...items];
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}

/** What gets saved: blank entries left out, as the API would. */
export function forSaving(cv: CvContent): CvContent {
  return {
    ...cv,
    links: cv.links.filter(Boolean),
    experience: cv.experience.filter((e) => e.title.trim()).map((e) => ({ ...e, bullets: e.bullets.filter((b) => b.trim()) })),
    education: cv.education.filter((e) => e.qualification.trim()),
    languages: cv.languages.filter((l) => l.name.trim()),
  };
}

export function sameCv(a: CvContent, b: CvContent): boolean {
  return JSON.stringify(forSaving(a)) === JSON.stringify(forSaving(b));
}

export function fileSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} bytes` : bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function describeDocument(doc: CvDocument): string {
  if (doc.status === "queued") return "Being made...";
  if (doc.status === "failed") return `Couldn't be made: ${doc.error || "unknown error"}`;
  return `${doc.pages} ${doc.pages === 1 ? "page" : "pages"} · ${fileSize(doc.size_bytes)}`;
}
