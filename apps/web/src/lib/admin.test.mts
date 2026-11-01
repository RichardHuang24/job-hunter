import { test } from "node:test";
import assert from "node:assert/strict";
import { budgetTone, compact, duration, percent, sourceHealth, usd } from "./admin.ts";

test("money and numbers", () => {
  assert.equal(usd(0), "$0");
  assert.equal(usd(0.0007), "$0.0007");
  assert.equal(usd(12.5), "$12.50");
  assert.equal(usd(1234.567), "$1,234.57");
  assert.equal(compact(1284), "1,284");
  assert.equal(compact(12_900), "12.9K");
  assert.equal(compact(4_200_000), "4.2M");
  assert.equal(percent(0.256), "26%");
  assert.equal(percent(null), "-");
});

test("durations", () => {
  assert.equal(duration(0), "0 s");
  assert.equal(duration(300), "5 min");
  assert.equal(duration(7200), "2 h");
  assert.equal(duration(3 * 86_400), "3 days");
});

test("a source's health is words and an icon", () => {
  assert.deepEqual(sourceHealth({ runs: 0, failed: 0, error_rate: null }), { label: "Not asked", icon: "–", tone: "none" });
  assert.equal(sourceHealth({ runs: 10, failed: 0, error_rate: 0 }).label, "Healthy");
  assert.equal(sourceHealth({ runs: 10, failed: 2, error_rate: 0.2 }).label, "Some failures");
  assert.equal(sourceHealth({ runs: 10, failed: 5, error_rate: 0.5 }).label, "Failing");
});

test("the budget meter", () => {
  assert.equal(budgetTone(null), "accent");
  assert.equal(budgetTone(0.5), "accent");
  assert.equal(budgetTone(0.85), "warning");
  assert.equal(budgetTone(1.2), "critical");
});
