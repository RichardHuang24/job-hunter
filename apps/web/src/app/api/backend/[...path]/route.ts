// The browser's door to the API: /api/backend/<path> -> the API's /<path>, as
// the signed-in user. No session, no request (401).
import { NextResponse, type NextRequest } from "next/server";
import { auth } from "@/auth";
import { backendFetch } from "@/lib/backend";
import { FORWARDED_HEADERS, backendPath } from "@/lib/backendPath";

async function forward(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) return NextResponse.json({ detail: "Not signed in." }, { status: 401 });
  const path = backendPath((await params).path, request.nextUrl.search);
  if (!path) return NextResponse.json({ detail: "Not found." }, { status: 404 });

  const headers: Record<string, string> = {};
  const type = request.headers.get("content-type");
  if (type) headers["content-type"] = type;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await backendFetch(userId, path, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
    });
  } catch (error) {
    console.error(`API ${request.method} ${path} failed:`, error);
    return NextResponse.json({ detail: "The API isn't reachable right now." }, { status: 502 });
  }
  const out = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  return new NextResponse(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: out });
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
