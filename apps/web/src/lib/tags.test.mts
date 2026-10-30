import { test } from "node:test";
import assert from "node:assert/strict";
import { addTags, remaining, removeAt } from "./tags.ts";

test("typed entries are trimmed, split and de-duplicated", () => {
  assert.deepEqual(addTags(["Python"], "  sql ,python, Docker;;"), ["Python", "sql", "Docker"]);
  assert.deepEqual(addTags([], "Washington, DC", { split: false }), ["Washington, DC"]);
  assert.deepEqual(addTags(["a", "b"], "c, d", { max: 3 }), ["a", "b", "c"]);
  assert.deepEqual(addTags(["a"], "   "), ["a"]);
});

test("removing and the suggestions left", () => {
  assert.deepEqual(removeAt(["a", "b", "c"], 1), ["a", "c"]);
  assert.deepEqual(remaining(["London", "Leeds", "Remote (UK)"], ["london"]), ["Leeds", "Remote (UK)"]);
});
