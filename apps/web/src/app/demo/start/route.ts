// Starts a demo account (DEMO_MODE=true): makes a fresh user and an Auth.js
// session for them, has the API set them up as the chosen fictional person
// (POST /demo/seed), and signs the browser in. Demo accounts live at
// demo.invalid, which can't receive email, and the worker deletes them after
// DEMO_ACCOUNT_HOURS.
import { randomBytes, randomUUID } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend";
import { pool } from "@/lib/db";
import { DEMO_EMAIL_DOMAIN, demoMode, sameOrigin, sessionCookieName, StartLimiter } from "@/lib/demo";

const limiter = new StartLimiter(20, 60 * 60 * 1000); // per address, per hour
const HOURS = Number(process.env.DEMO_ACCOUNT_HOURS || 24);

function back(request: NextRequest, error: string): NextResponse {
  return NextResponse.redirect(new URL(`/signin?error=${encodeURIComponent(error)}`, request.url), 303);
}

export async function POST(request: NextRequest) {
  if (!demoMode()) return NextResponse.json({ detail: "Not found." }, { status: 404 });
  if (!sameOrigin(request.headers.get("origin"), request.headers.get("host"), request.headers.get("x-forwarded-host"))) {
    return NextResponse.json({ detail: "Start the demo from its sign-in page." }, { status: 403 });
  }
  const address = (request.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "unknown";
  if (!limiter.allow(address)) return back(request, "DemoBusy");
  const person = String((await request.formData()).get("person") ?? "");

  const token = randomBytes(32).toString("hex");
  const expires = new Date(Date.now() + HOURS * 3600 * 1000);
  let userId: string;
  try {
    const user = await pool.query<{ id: number }>("INSERT INTO users (name, email) VALUES ($1, $2) RETURNING id", [
      "Demo",
      `demo-${randomUUID().slice(0, 12)}@${DEMO_EMAIL_DOMAIN}`,
    ]);
    userId = String(user.rows[0].id);
    await pool.query('INSERT INTO sessions ("userId", expires, "sessionToken") VALUES ($1, $2, $3)', [userId, expires, token]);
  } catch (error) {
    console.error("Couldn't make a demo account:", error);
    return back(request, "DemoFailed");
  }

  const seeded = await backendFetch(userId, "/demo/seed", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ person }),
  }).catch(() => null);
  if (!seeded || seeded.status !== 204) {
    await pool.query("DELETE FROM users WHERE id = $1", [userId]).catch(() => undefined);
    return back(request, seeded?.status === 429 ? "DemoBusy" : "DemoFailed");
  }

  const secure = (process.env.AUTH_URL ?? request.url).startsWith("https:");
  const response = NextResponse.redirect(new URL("/", request.url), 303);
  response.cookies.set(sessionCookieName(secure), token, { httpOnly: true, sameSite: "lax", path: "/", secure, expires });
  return response;
}
