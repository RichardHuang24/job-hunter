// Which API path a /api/backend/... request may reach - pure, tested in
// backendPath.test.mts. Only plain path segments get through: no "..", no
// encoded slashes, nothing that could point the request somewhere else.

const SEGMENT = /^[A-Za-z0-9._~-]+$/;

export function backendPath(segments: string[], search = ""): string | null {
  if (!segments.length) return null;
  for (const segment of segments) {
    if (!SEGMENT.test(segment) || segment === "." || segment === "..") return null;
  }
  const query = search && search !== "?" ? (search.startsWith("?") ? search : `?${search}`) : "";
  return `/${segments.join("/")}${query}`;
}

/** Response headers worth passing back to the browser. */
export const FORWARDED_HEADERS = ["content-type", "content-disposition", "cache-control"];
