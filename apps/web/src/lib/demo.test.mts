import { test } from "node:test";
import assert from "node:assert/strict";
import { sameOrigin, sessionCookieName, StartLimiter } from "./demo.ts";

test("the session cookie's name", () => {
  assert.equal(sessionCookieName(false), "authjs.session-token");
  assert.equal(sessionCookieName(true), "__Secure-authjs.session-token");
});

test("only this site can start a demo", () => {
  assert.ok(sameOrigin("https://demo.example.com", "demo.example.com"));
  assert.ok(sameOrigin("https://demo.example.com", "web:3000", "demo.example.com")); // behind Caddy
  assert.ok(!sameOrigin("https://evil.example", "demo.example.com"));
  assert.ok(!sameOrigin(null, "demo.example.com"));
  assert.ok(!sameOrigin("not a url", "demo.example.com"));
});

test("starts are limited per address", () => {
  const limiter = new StartLimiter(2, 60_000);
  assert.ok(limiter.allow("1.2.3.4", 0));
  assert.ok(limiter.allow("1.2.3.4", 1));
  assert.ok(!limiter.allow("1.2.3.4", 2));
  assert.ok(limiter.allow("5.6.7.8", 2));
  assert.ok(limiter.allow("1.2.3.4", 60_001)); // the window moved on
});
