import { test } from "node:test";
import assert from "node:assert/strict";
import { daysAgo, runSummary, salaryRange, since } from "./jobs.ts";
import type { Run } from "./types.ts";

test("salary ranges", () => {
  assert.equal(salaryRange(31000, 37000, "GBP", "year"), "£31,000–£37,000 a year");
  assert.equal(salaryRange(13, 13, "GBP", "hour"), "£13 an hour");
  assert.equal(salaryRange(null, 50000, "EUR", "year"), "€50,000 a year");
  assert.equal(salaryRange(null, null, "GBP", "year"), "");
  assert.equal(salaryRange(1, 2, "", "year"), "");
});

test("dates, by the day and by the minute", () => {
  const now = new Date("2026-10-31T12:00:00Z");
  assert.equal(daysAgo("2026-10-31T01:00:00Z", now), "today");
  assert.equal(daysAgo("2026-10-30T23:00:00Z", now), "yesterday");
  assert.equal(daysAgo("2026-10-25T09:00:00Z", now), "6 days ago");
  assert.equal(daysAgo("2026-10-10T09:00:00Z", now), "3 weeks ago");
  assert.equal(since("2026-10-31T11:59:40Z", now), "just now");
  assert.equal(since("2026-10-31T11:59:00Z", now), "1 minute ago");
  assert.equal(since("2026-10-31T09:00:00Z", now), "3 hours ago");
  assert.equal(since("2026-10-29T09:00:00Z", now), "2 days ago");
  assert.equal(daysAgo(null, now), "");
});

test("run summaries", () => {
  const run = (status: Run["status"], counts: Run["counts"] = {}): Run => ({
    id: "r", search_id: "s", status, trigger: "manual", counts, errors: [], created_at: "", started_at: null, finished_at: null,
  });
  assert.equal(runSummary(run("succeeded", { new: 6, matches: 4 })), "6 new jobs, 4 matches in all");
  assert.equal(runSummary(run("succeeded", { new: 1, matches: 1 })), "1 new job, 1 match in all");
  assert.equal(runSummary(run("succeeded", { new: 0 })), "Nothing new");
  assert.equal(runSummary(run("queued")), "Waiting to start");
  assert.equal(runSummary(run("failed")), "The search failed");
});
