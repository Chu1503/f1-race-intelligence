// const API = "http://localhost:8000";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Retries up to `attempts` times with exponential backoff and a per-request timeout.
async function fetchWithRetry(
  url: string,
  options?: RequestInit,
  attempts = 2,
  timeoutMs = 8_000
): Promise<Response> {
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      const res = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timer);
      return res;
    } catch (err) {
      lastError = err;
      if (i < attempts - 1) {
        await new Promise(r => setTimeout(r, 500));
      }
    }
  }
  throw lastError;
}

// ── API functions ──────────────────────────────────────────────────────────

export async function pingHealth(): Promise<boolean> {
  try {
    const res = await fetchWithRetry(`${API}/health`, undefined, 1, 10_000);
    return res.ok;
  } catch { return false; }
}

export async function getAvailableRaces() {
  try {
    const res = await fetchWithRetry(`${API}/available-races`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getSeasons() {
  try {
    const res = await fetchWithRetry(`${API}/seasons`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getCalendar(year: number) {
  try {
    const res = await fetchWithRetry(`${API}/calendar/${year}`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getDriversForYear(year: number) {
  try {
    const res = await fetchWithRetry(`${API}/drivers/${year}`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getLaps(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/laps`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getRaceDriverStats(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/drivers`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getRaceResults(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/results`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getRaceIncidents(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/incidents`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getLapPositions(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/lap-positions`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getFastestLaps(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/fastest-laps`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getTyreStrategies(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/tyre-strategies`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getPitStops(year: number, round: number) {
  try {
    const res = await fetchWithRetry(`${API}/race/${year}/${round}/pit-stops`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function runBatchProcessor(year: number, round: number) {
  try {
    const res = await fetchWithRetry(
      `${API}/batch/process?year=${year}&round_number=${round}`,
      { method: "POST" }
    );
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getStrategy(payload: object) {
  try {
    const res = await fetchWithRetry(`${API}/strategy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, 1, 90_000); // 1 attempt, 90s timeout — LLM + cold start on Render
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export async function getCommentary(payload: object) {
  try {
    const res = await fetchWithRetry(`${API}/commentary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, 1, 90_000); // 1 attempt, 90s timeout — LLM + cold start on Render
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

export type { };

export interface DriverInfo {
  driver_number: number;
  code: string;
  full_name: string;
  team: string;
  color: string;
  nationality: string;
}