import { test } from "node:test";
import assert from "node:assert/strict";
import { appViews, day, due, todayIso, viewCount } from "./applications.ts";

const statuses = [
  { key: "planned", label: "To apply" }, { key: "applied", label: "Applied" }, { key: "interviewing", label: "Interviewing" },
  { key: "offer", label: "Offer" }, { key: "rejected", label: "Rejected" },
];

test("the tabs", () => {
  const views = appViews(statuses);
  assert.deepEqual(views.map((v) => v.label), ["Active", "To apply", "Applied", "Interviewing", "Offer", "Closed", "All"]);
  const counts = { active: 3, closed: 2, by_status: { planned: 1, applied: 2, rejected: 2 } };
  assert.deepEqual(views.map((v) => viewCount(v.key, counts)), [3, 1, 2, 0, 0, 2, 5]);
});

test("days and how soon", () => {
  const now = new Date("2026-11-01T15:00:00Z");
  assert.equal(todayIso(now), "2026-11-01");
  assert.equal(day("2026-11-12", now), "12 Nov");
  assert.equal(day("2025-12-03", now), "3 Dec 2025");
  assert.deepEqual(due("2026-10-30", now), { text: "Overdue - 30 Oct", tone: "late" });
  assert.deepEqual(due("2026-11-01", now), { text: "Today", tone: "soon" });
  assert.deepEqual(due("2026-11-02", now), { text: "Tomorrow", tone: "soon" });
  assert.deepEqual(due("2026-11-20", now), { text: "20 Nov", tone: "later" });
});
