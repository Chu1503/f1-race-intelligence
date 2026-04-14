const API = "http://localhost:8000";

export async function getAvailableRaces() {
  const res = await fetch(`${API}/available-races`);
  return res.json();
}

export async function getSeasons() {
  const res = await fetch(`${API}/seasons`);
  return res.json();
}

export async function getCalendar(year: number) {
  const res = await fetch(`${API}/calendar/${year}`);
  if (!res.ok) return null;
  return res.json();
}

export async function getDriversForYear(year: number) {
  const res = await fetch(`${API}/drivers/${year}`);
  if (!res.ok) return null;
  return res.json();
}

export async function getLaps(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/laps`);
  if (!res.ok) return null;
  return res.json();
}

export async function getRaceDriverStats(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/drivers`);
  if (!res.ok) return null;
  return res.json();
}

export async function getRaceResults(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/results`);
  if (!res.ok) return null;
  return res.json();
}

export async function getRaceIncidents(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/incidents`);
  if (!res.ok) return null;
  return res.json();
}

export async function getLapPositions(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/lap-positions`);
  if (!res.ok) return null;
  return res.json();
}

export async function getFastestLaps(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/fastest-laps`);
  if (!res.ok) return null;
  return res.json();
}

export async function getTyreStrategies(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/tyre-strategies`);
  if (!res.ok) return null;
  return res.json();
}

export async function getPitStops(year: number, round: number) {
  const res = await fetch(`${API}/race/${year}/${round}/pit-stops`);
  if (!res.ok) return null;
  return res.json();
}

export async function runBatchProcessor(year: number, round: number) {
  const res = await fetch(
    `${API}/batch/process?year=${year}&round_number=${round}`,
    { method: "POST" }
  );
  return res.json();
}

export async function getStrategy(payload: object) {
  const res = await fetch(`${API}/strategy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function getCommentary(payload: object) {
  const res = await fetch(`${API}/commentary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
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