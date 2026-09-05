"use client";

import { useCallback, useEffect, useState } from "react";
import { getTeamColor, type CalendarRace, type SessionDriver } from "../lib/constants";
import {
  errorMessage, getCalendar, getDriversForYear, getFastestLaps, getLapPositions,
  getLaps, getPitStops, getRaceDriverStats, getRaceIncidents, getRaceResults,
  getTyreStrategies, type DriverInfo,
} from "../lib/api";
import type { DriverStat, FastestLap, Incident, LapPosition, LapRow, PitStop, RaceResult, TyreStrategy } from "../components/race/types";

function buildSessionDrivers(fl: FastestLap[], pos: LapPosition[], ts: TyreStrategy[], drivers: Record<string, DriverInfo>, results: RaceResult[]): Record<number, SessionDriver> {
  const map: Record<number, SessionDriver> = {};
  const resultByCode = Object.fromEntries(results.map((result) => [result.abbreviation, result]));
  for (const result of results) {
    if (!result.driver_number) continue;
    map[result.driver_number] = { race_number: result.driver_number, code: result.abbreviation, full_name: result.full_name, team: result.team, color: getTeamColor(result.team) };
  }
  const pairs: { num: number; code: string }[] = fl.map((item) => ({ num: item.driver_number, code: item.driver_code }));
  for (const item of pos) if (!pairs.some(({ num }) => num === item.DriverNumber)) pairs.push({ num: item.DriverNumber, code: item.Driver });
  for (const item of ts) if (!pairs.some(({ num }) => num === item.driver_number)) pairs.push({ num: item.driver_number, code: item.driver_code });
  for (const { num, code } of pairs) {
    const result = resultByCode[code];
    const team = result?.team || drivers[code]?.team || map[num]?.team || "";
    map[num] = { race_number: num, code, full_name: result?.full_name || drivers[code]?.full_name || map[num]?.full_name || code, team, color: getTeamColor(team) };
  }
  return map;
}

export function useRaceData(year: number, round: number) {
  const [calendar, setCalendar] = useState<CalendarRace[]>([]);
  const [laps, setLaps] = useState<LapRow[] | null>(null);
  const [driverStats, setDriverStats] = useState<DriverStat[]>([]);
  const [results, setResults] = useState<RaceResult[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [lapPositions, setLapPositions] = useState<LapPosition[]>([]);
  const [fastestLaps, setFastestLaps] = useState<FastestLap[]>([]);
  const [tyreStrategies, setTyreStrategies] = useState<TyreStrategy[]>([]);
  const [pitStops, setPitStops] = useState<PitStop[]>([]);
  const [sdByNum, setSdByNum] = useState<Record<number, SessionDriver>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError(""); setLaps(null);
    try {
      const [cal, driverResponse, lapRows, stats, resultResponse, incidentResponse, positions, fastest, strategies, stops] = await Promise.all([
        getCalendar(year), getDriversForYear(year), getLaps<LapRow[]>(year, round), getRaceDriverStats<DriverStat[]>(year, round),
        getRaceResults<{ results: RaceResult[] }>(year, round), getRaceIncidents<{ incidents: Incident[] }>(year, round),
        getLapPositions<LapPosition[]>(year, round), getFastestLaps<FastestLap[]>(year, round),
        getTyreStrategies<TyreStrategy[]>(year, round), getPitStops<PitStop[]>(year, round),
      ]);
      const drivers = Object.fromEntries(driverResponse.drivers.map((driver) => [driver.code, driver]));
      setCalendar(cal.races); setLaps(lapRows); setDriverStats(stats); setResults(resultResponse.results);
      setIncidents(incidentResponse.incidents); setLapPositions(positions); setFastestLaps(fastest); setTyreStrategies(strategies); setPitStops(stops);
      setSdByNum(buildSessionDrivers(fastest, positions, strategies, drivers, resultResponse.results));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally { setLoading(false); }
  }, [year, round]);

  useEffect(() => { void load(); }, [load]);
  return { calendar, laps, driverStats, results, incidents, lapPositions, fastestLaps, tyreStrategies, pitStops, sdByNum, loading, error, retry: load };
}
