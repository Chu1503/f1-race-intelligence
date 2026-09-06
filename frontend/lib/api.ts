// Keep browser requests same-origin. The Next route forwards them to Render (or
// localhost in development), avoiding CORS/ad-blocker failures and giving a
// sleeping backend enough time to start.
const API = "/api/data";
const DEFAULT_TIMEOUT_MS = process.env.NODE_ENV === "production" ? 100_000 : 8_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchWithRetry(url: string, options?: RequestInit, attempts = 3, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      if (![502, 503, 504].includes(response.status) || attempt === attempts - 1) return response;
      lastError = new ApiError(`The data service is starting (${response.status}).`, response.status);
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
    } finally {
      clearTimeout(timer);
    }
  }
  if (lastError instanceof DOMException && lastError.name === "AbortError") {
    throw new ApiError("The data service timed out. Please try again.", 408);
  }
  throw new ApiError("The data service is unreachable. Please try again.", 0);
}

async function requestJson<T>(url: string, options?: RequestInit, attempts = 3, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const response = await fetchWithRetry(url, options, attempts, timeoutMs);
  const body = await response.json().catch(() => ({})) as { detail?: string; message?: string };
  if (!response.ok) {
    throw new ApiError(
      body.detail || body.message || `Request failed (${response.status})`,
      response.status,
      Number(response.headers.get("retry-after")) || undefined,
    );
  }
  return body as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export interface AvailableRace { year: number; round: number }
export interface ProcessingJob {
  id: string;
  year: number;
  round_number: number;
  status: "queued" | "running" | "succeeded" | "failed";
  message: string;
  error?: string | null;
  rows_written?: number | null;
}

export const getAvailableRaces = () => requestJson<{ races: AvailableRace[] }>(`${API}/available-races`);
export const getSeasons = () => requestJson<{ seasons: number[] }>(`${API}/seasons`);
export const getCalendar = (year: number) => requestJson<{ year: number; races: import("./constants").CalendarRace[] }>(`${API}/calendar/${year}`);
export const getDriversForYear = (year: number) => requestJson<{ year: number; drivers: DriverInfo[] }>(`${API}/drivers/${year}`);
export const getLaps = <T = unknown[]>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/laps`);
export const getRaceDriverStats = <T = unknown[]>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/drivers`);
export const getRaceResults = <T = unknown>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/results`);
export const getRaceIncidents = <T = unknown>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/incidents`);
export const getLapPositions = <T = unknown[]>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/lap-positions`);
export const getFastestLaps = <T = unknown[]>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/fastest-laps`);
export const getTyreStrategies = <T = unknown[]>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/tyre-strategies`);
export const getPitStops = <T = unknown[]>(year: number, round: number) => requestJson<T>(`${API}/race/${year}/${round}/pit-stops`);

export const runBatchProcessor = (year: number, roundNumber: number) => requestJson<ProcessingJob>(
  "/api/processing/jobs",
  { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ year, round_number: roundNumber }) },
  1,
  30_000,
);
export const getProcessingJob = (jobId: string) => requestJson<ProcessingJob>(`/api/processing/jobs/${encodeURIComponent(jobId)}`, undefined, 1, 15_000);
export const getStrategy = <T = { recommendation: string; rag_sources?: unknown[] }>(payload: object) => requestJson<T>(
  "/api/ai/strategy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, 1, 120_000,
);
export const getCommentary = <T = { commentary: string }>(payload: object) => requestJson<T>(
  "/api/ai/commentary", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, 1, 120_000,
);

export interface DriverInfo {
  driver_number: number;
  code: string;
  full_name: string;
  team: string;
  color: string;
  nationality: string;
}
