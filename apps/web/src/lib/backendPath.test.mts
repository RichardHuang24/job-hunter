import { test } from "node:test";
import assert from "node:assert/strict";
import { backendPath } from "./backendPath.ts";

test("plain segments and the query pass through", () => {
  assert.equal(backendPath(["me"]), "/me");
  assert.equal(backendPath(["me", "profile"], "?a=1&b=2"), "/me/profile?a=1&b=2");
  assert.equal(backendPath(["jobs"], "limit=5"), "/jobs?limit=5");
  assert.equal(backendPath(["me"], "?"), "/me");
});

test("anything that could escape the API's paths is refused", () => {
  assert.equal(backendPath([]), null);
  assert.equal(backendPath([".."]), null);
  assert.equal(backendPath(["me", ".."]), null);
  assert.equal(backendPath(["a%2Fb"]), null);
  assert.equal(backendPath(["http:", "", "evil.example"]), null);
  assert.equal(backendPath(["me profile"]), null);
});
