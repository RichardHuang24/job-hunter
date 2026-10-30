import { test } from "node:test";
import assert from "node:assert/strict";
import { emptyProfile, formatSalary, listOf, parseAmount, toWrite } from "./profile.ts";

const ARRANGEMENTS = [
  { key: "onsite", label: "On-site" },
  { key: "hybrid", label: "Hybrid" },
  { key: "remote", label: "Remote" },
];

test("amounts the way people type them", () => {
  assert.equal(parseAmount("32,000"), 32000);
  assert.equal(parseAmount(" £45k "), 45000);
  assert.equal(parseAmount("17.5"), 18);
  assert.equal(parseAmount(""), null);
  assert.ok(Number.isNaN(parseAmount("lots")));
});

test("lists read as a sentence, in the options' order", () => {
  assert.equal(listOf(ARRANGEMENTS, ["remote", "onsite"]), "On-site or remote");
  assert.equal(listOf(ARRANGEMENTS, ["remote", "hybrid", "onsite"], "and"), "On-site, hybrid and remote");
  assert.equal(listOf(ARRANGEMENTS, ["hybrid"]), "Hybrid");
  assert.equal(listOf(ARRANGEMENTS, []), "");
});

test("salaries", () => {
  const periods = [{ key: "year", label: "per year" }];
  assert.equal(formatSalary(32000, "GBP", "year", periods), "£32,000 per year");
  assert.equal(formatSalary(18, "EUR", "hour"), "€18 per hour");
});

test("a profile from the API becomes a write without its timestamps", () => {
  const write = toWrite({ ...emptyProfile(), industry: "legal", onboarded_at: "2026-10-30T00:00:00Z", updated_at: "x" });
  assert.equal(write.industry, "legal");
  assert.ok(!("onboarded_at" in write) && !("updated_at" in write));
  assert.deepEqual(toWrite(null), emptyProfile());
});
