// Calling the API on a signed-in user's behalf. The browser never talks to
// the API: this server signs a 60-second token naming the user (`sub`) with
// BACKEND_JWT_SECRET, which the API checks (apps/api/app/auth.py).
import { SignJWT } from "jose";

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8420";
const encoder = new TextEncoder();

export async function backendToken(userId: string): Promise<string> {
  const secret = process.env.BACKEND_JWT_SECRET ?? "";
  if (secret.length < 32) throw new Error("BACKEND_JWT_SECRET must be set to at least 32 characters.");
  return new SignJWT({})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuer("job-hunter-web")
    .setAudience("job-hunter-api")
    .setIssuedAt()
    .setExpirationTime("60s")
    .sign(encoder.encode(secret));
}

/** A server-side request to the API as `userId` (server components, route handlers). */
export async function backendFetch(userId: string, path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${await backendToken(userId)}`);
  if (!headers.has("accept")) headers.set("accept", "application/json");
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers, cache: "no-store" });
}

/** The few API answers that aren't about anyone (the privacy page's facts): no token. */
export async function backendPublic<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${BACKEND_URL}${path}`, { headers: { accept: "application/json" }, cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}
