import "server-only";

const BACKEND = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

async function fetchBackend(path: string, init: RequestInit): Promise<Response> {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetch(`${BACKEND}${path}`, { ...init, cache: "no-store" });
      if (![502, 503, 504].includes(response.status) || attempt === 2) return response;
    } catch {
      if (attempt === 2) break;
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000 * (attempt + 1)));
  }
  return Response.json({ detail: "The backend service is unreachable." }, { status: 502 });
}

export async function forwardPublic(path: string): Promise<Response> {
  return fetchBackend(path, { method: "GET" });
}

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
  return fetchBackend(path, { method: request?.method || "GET", headers, body });
}
