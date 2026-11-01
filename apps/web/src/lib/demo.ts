// Demo mode (DEMO_MODE=true, apps/api/app/demo.py): the pieces the web app
// needs to start a demo account. Pure, so they're tested on their own.

export const DEMO_EMAIL_DOMAIN = "demo.invalid";

export function demoMode(): boolean {
  return process.env.DEMO_MODE === "true";
}

/** Auth.js's session cookie: __Secure- prefixed when the site is on https. */
export function sessionCookieName(secure: boolean): string {
  return `${secure ? "__Secure-" : ""}authjs.session-token`;
}

/** A browser's form post from this site, not from another one (no cross-site sign-in). */
export function sameOrigin(origin: string | null, host: string | null, forwardedHost?: string | null): boolean {
  if (!origin) return false;
  try {
    const from = new URL(origin).host;
    return from === (forwardedHost || host);
  } catch {
    return false;
  }
}

/** At most `limit` starts per key (an IP address) in `windowMs`. In memory: one web process. */
export class StartLimiter {
  private hits = new Map<string, number[]>();
  private readonly limit: number;
  private readonly windowMs: number;

  constructor(limit: number, windowMs: number) {
    this.limit = limit;
    this.windowMs = windowMs;
  }

  allow(key: string, now = Date.now()): boolean {
    const recent = (this.hits.get(key) ?? []).filter((t) => now - t < this.windowMs);
    if (recent.length >= this.limit) {
      this.hits.set(key, recent);
      return false;
    }
    recent.push(now);
    this.hits.set(key, recent);
    if (this.hits.size > 10_000) this.hits.clear(); // never grows without bound
    return true;
  }
}
