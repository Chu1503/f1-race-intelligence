import "server-only";

const BACKEND = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";
const REPRESENTATION_HEADERS = [
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
  "keep-alive",
];

function relayResponse(response: Response, cacheControl: string): Response {
  const headers = new Headers(response.headers);
  // Next's server fetch decodes compressed bodies. Forwarding the original
  // encoding/length would describe bytes that are no longer in the response.
  for (const header of REPRESENTATION_HEADERS) headers.delete(header);
  headers.set("Cache-Control", response.ok ? cacheControl : "no-store");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function fetchBackend(path: string, init: RequestInit, cacheControl: string): Promise<Response> {
  const operation = path.split("?", 1)[0];
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const started = performance.now();
    try {
      const response = await fetch(`${BACKEND}${path}`, { ...init, cache: "no-store" });
      if (process.env.NODE_ENV !== "production") {
        console.info(`[perf] backend ${init.method || "GET"} ${operation} attempt=${attempt + 1} ${Math.round(performance.now() - started)}ms`);
      }
      if (![502, 503, 504].includes(response.status) || attempt === 2) {
        return relayResponse(response, cacheControl);
      }
    } catch {
      if (process.env.NODE_ENV !== "production") {
        console.info(`[perf] backend ${init.method || "GET"} ${operation} attempt=${attempt + 1} failed ${Math.round(performance.now() - started)}ms`);
      }
      if (attempt === 2) break;
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000 * (attempt + 1)));
  }
  return Response.json(
    { detail: "The backend service is unreachable." },
    { status: 502, headers: { "Cache-Control": "no-store" } },
  );
}

export async function forwardPublic(path: string): Promise<Response> {
  return fetchBackend(
    path,
    { method: "GET" },
    "public, max-age=0, s-maxage=300, stale-while-revalidate=86400",
  );
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
  return fetchBackend(
    path,
    { method: request?.method || "GET", headers, body },
    "private, no-store",
  );
}
