// Browser-side calls to the API, through this app's /api/backend door
// (app/api/backend/[...path]/route.ts adds the signed-in user).

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** FastAPI's `detail` - a sentence, or a list of field errors - as one sentence. */
function message(detail: unknown, status: number): string {
  if (status === 401) return "You've been signed out. Sign in again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const field = first.loc?.at(-1);
    return field ? `${String(field).replace(/_/g, " ")}: ${first.msg}` : (first.msg ?? `Request failed (${status}).`);
  }
  return `Request failed (${status}).`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  const response = await fetch(`/api/backend${path}`, { ...init, headers });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(message(detail, response.status), response.status);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}
