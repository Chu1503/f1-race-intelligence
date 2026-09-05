import "server-only";

const BACKEND = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function forwardProtected(path: string, request?: Request): Promise<Response> {
  const serviceKey = process.env.API_SERVICE_KEY;
  if (!serviceKey && process.env.NODE_ENV === "production") {
    return Response.json({ detail: "AI and processing routes are not configured." }, { status: 503 });
  }
  const headers = new Headers({ "X-API-Key": serviceKey || "" });
  let body: string | undefined;
  if (request && request.method !== "GET" && request.method !== "HEAD") {
    headers.set("Content-Type", request.headers.get("content-type") || "application/json");
    body = await request.text();
  }
  try {
    return await fetch(`${BACKEND}${path}`, { method: request?.method || "GET", headers, body, cache: "no-store" });
  } catch {
    return Response.json({ detail: "The backend service is unreachable." }, { status: 502 });
  }
}
