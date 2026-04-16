import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import threading
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from loguru import logger
from logger_config import setup_logging
from datetime import datetime
import unicodedata

setup_logging()

app = FastAPI(title="F1 Race Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://f1-race-intelligence.vercel.app",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEAM_COLORS = {
    "red bull":       "#3671C6",
    "ferrari":        "#E8002D",
    "mercedes":       "#27F4D2",
    "mclaren":        "#FF8000",
    "aston martin":   "#229971",
    "alpine":         "#FF87BC",
    "williams":       "#64C4FF",
    "rb":             "#6692FF",
    "racing bulls":   "#6692FF",
    "kick sauber":    "#52E252",
    "sauber":         "#52E252",
    "haas":           "#B6BABD",
    "audi":           "#BB0000",
    "cadillac":       "#1F3275",
    "andretti":       "#1F3275",
    "general motors": "#1F3275",
}

def team_color(team_name: str) -> str:
    if not team_name:
        return "#888888"
    t = team_name.lower()
    for key, color in TEAM_COLORS.items():
        if key in t:
            return color
    return "#888888"


_driver_cache: dict = {}
_calendar_cache: dict = {}
_results_cache: dict = {}

_DISK_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jolpica_cache")
os.makedirs(_DISK_CACHE_DIR, exist_ok=True)

def _disk_cache_read(key: str):
    import json
    path = os.path.join(_DISK_CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None

def _disk_cache_write(key: str, data):
    import json
    path = os.path.join(_DISK_CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def fetch_drivers_for_year(year: int) -> list:
    if year in _driver_cache:
        return _driver_cache[year]
    cached = _disk_cache_read(f"drivers_{year}")
    if cached is not None:
        _driver_cache[year] = cached
        return cached
    try:
        r = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/drivers.json", timeout=10
        )
        drivers_raw = r.json()["MRData"]["DriverTable"]["Drivers"]

        standings_r = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/driverStandings.json", timeout=10
        )
        standings_data = standings_r.json()["MRData"]["StandingsTable"]["StandingsLists"]
        team_map = {}
        if standings_data:
            for entry in standings_data[0]["DriverStandings"]:
                code = entry["Driver"]["code"]
                team_map[code] = (
                    entry["Constructors"][0]["name"] if entry["Constructors"] else "Unknown"
                )

        drivers = []
        for d in drivers_raw:
            code = d.get("code", "???")
            team = team_map.get(code, "Unknown")
            drivers.append({
                "driver_number": int(d.get("permanentNumber", 0)),
                "code": code,
                "full_name": f"{d['givenName']} {d['familyName']}",
                "team": team,
                "color": team_color(team),
                "nationality": d.get("nationality", ""),
            })

        _driver_cache[year] = drivers
        _disk_cache_write(f"drivers_{year}", drivers)
        return drivers
    except Exception as e:
        logger.warning(f"Could not fetch live drivers for {year}: {e}")
        return []


def fetch_calendar_for_year(year: int) -> list:
    if year in _calendar_cache:
        return _calendar_cache[year]
    cached = _disk_cache_read(f"calendar_{year}")
    if cached is not None:
        _calendar_cache[year] = cached
        return cached
    try:
        r = requests.get(f"https://api.jolpi.ca/ergast/f1/{year}.json", timeout=10)
        races_raw = r.json()["MRData"]["RaceTable"]["Races"]
        races = []
        for race in races_raw:
            races.append({
                "round": int(race["round"]),
                "name": race["raceName"].replace(" Grand Prix", ""),
                "full_name": race["raceName"],
                "circuit": race["Circuit"]["circuitName"],
                "country": race["Circuit"]["Location"]["country"],
                "locality": race["Circuit"]["Location"]["locality"],
                "date": race.get("date", ""),
            })
        _calendar_cache[year] = races
        _disk_cache_write(f"calendar_{year}", races)
        return races
    except Exception as e:
        logger.warning(f"Could not fetch calendar for {year}: {e}")
        return []


def fetch_results_from_jolpica(year: int, round_number: int) -> list:
    cache_key = f"{year}_{round_number}"
    if cache_key in _results_cache:
        return _results_cache[cache_key]
    try:
        r = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/{round_number}/results.json",
            timeout=10,
        )
        data = r.json()["MRData"]["RaceTable"]["Races"]
        if not data:
            return []

        race = data[0]
        results = []
        for res in race["Results"]:
            driver = res["Driver"]
            constructor = res["Constructor"]
            status = res.get("status", "Unknown")
            results.append({
                "driver_number": int(driver.get("permanentNumber", 0)),
                "abbreviation": driver.get("code", "???"),
                "full_name": f"{driver['givenName']} {driver['familyName']}",
                "team": constructor["name"],
                "team_color": team_color(constructor["name"]),
                "grid_position": int(res.get("grid", 0)) or None,
                "finish_position": int(res.get("position", 0)) or None,
                "status": status,
                "points": float(res.get("points", 0)),
                "laps_completed": int(res.get("laps", 0)),
                "time": res.get("Time", {}).get("time", "") if res.get("Time") else "",
                "fastest_lap_time": (
                    res.get("FastestLap", {}).get("Time", {}).get("time", "")
                    if res.get("FastestLap") else ""
                ),
                "fastest_lap_rank": (
                    int(res.get("FastestLap", {}).get("rank", 0))
                    if res.get("FastestLap") else None
                ),
            })

        _results_cache[cache_key] = results
        return results
    except Exception as e:
        logger.warning(f"Jolpica results error for {year} R{round_number}: {e}")
        return []


def _get_fastf1_session(year: int, round_number: int):
    """Load a FastF1 session with caching."""
    import fastf1, warnings
    warnings.filterwarnings("ignore")
    from config import settings
    fastf1.Cache.enable_cache(str(settings.FASTF1_CACHE_DIR))
    session = fastf1.get_session(year, round_number, "R")
    session.load(telemetry=False, weather=False, messages=False)
    return session


class DriverSituation(BaseModel):
    driver_number: int
    lap_number: int
    lap_duration: float
    tyre_compound: str
    tyre_age_laps: int
    tyre_degradation_rate: Optional[float] = 0.0
    rolling_avg_lap_time: Optional[float] = None
    lap_delta: Optional[float] = None
    should_pit_soon: bool
    estimated_laps_to_pit: Optional[float] = 999.0
    position: Optional[int] = None
    gap_to_leader: Optional[float] = None
    circuit_name: str = "unknown"
    total_race_laps: int = 57


class CommentaryRequest(BaseModel):
    driver_name: str
    driver_number: int
    lap_number: int
    lap_duration: float
    tyre_compound: str
    tyre_age_laps: int
    should_pit_soon: bool
    tyre_degradation_rate: Optional[float] = 0.0
    position: Optional[int] = None
    strategy_recommendation: Optional[str] = None



@app.get("/")
def root():
    return {"status": "online", "service": "F1 Race Intelligence API"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/seasons")
def get_seasons():
    current = datetime.now().year
    return {"seasons": list(range(current, 2022, -1))}


@app.get("/calendar/{year}")
def get_calendar(year: int):
    return {"year": year, "races": fetch_calendar_for_year(year)}


@app.get("/drivers/{year}")
def get_drivers_for_year(year: int):
    return {"year": year, "drivers": fetch_drivers_for_year(year)}


@app.get("/available-races")
def get_available_races():
    base = "data/spark_output/historical"
    if not os.path.exists(base):
        return {"races": []}
    races = []
    for folder in os.listdir(base):
        match = re.match(r"(\d{4})_round(\d+)", folder)
        if match:
            races.append({"year": int(match.group(1)), "round": int(match.group(2))})
    return {"races": sorted(races, key=lambda x: (x["year"], x["round"]), reverse=True)}


@app.get("/race/{year}/{round_number}/laps")
def get_all_laps(year: int, round_number: int):
    try:
        path = f"data/spark_output/historical/{year}_round{round_number}"
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="No data found. Run batch processor first.")
        df = pd.read_parquet(path)
        df = df.replace({float("nan"): None, float("inf"): None, float("-inf"): None})
        return df.to_dict(orient="records")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/race/{year}/{round_number}/drivers")
def get_race_drivers(year: int, round_number: int):
    try:
        path = f"data/spark_output/historical/{year}_round{round_number}"
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="No data found.")
        df = pd.read_parquet(path)
        df = df.replace({float("nan"): None, float("inf"): None, float("-inf"): None})
        summary = (
            df.groupby("driver_number")
            .agg(
                total_laps=("lap_number", "count"),
                fastest_lap=("lap_duration", "min"),
                avg_lap_time=("lap_duration", "mean"),
                avg_deg_rate=("tyre_degradation_rate", "mean"),
                pit_flags=("should_pit_soon", "sum"),
            )
            .reset_index()
        )
        return summary.to_dict(orient="records")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/race/{year}/{round_number}/results")
def get_race_results(year: int, round_number: int):
    results = fetch_results_from_jolpica(year, round_number)
    if results:
        return {"results": results, "source": "jolpica"}

    try:
        session = _get_fastf1_session(year, round_number)
        res = session.results
        if res is None or res.empty:
            return {"results": [], "source": "none"}

        output = []
        for _, row in res.iterrows():
            def safe(val, cast=str, default=None):
                try:
                    v = cast(val)
                    return None if str(v) in ["nan", "None", "<NA>", ""] else v
                except Exception:
                    return default

            team = safe(row.get("TeamName"), str, "")
            output.append({
                "driver_number": safe(row.get("DriverNumber"), int, 0),
                "abbreviation": safe(row.get("Abbreviation"), str, ""),
                "full_name": safe(row.get("FullName"), str, ""),
                "team": team,
                "team_color": team_color(team or ""),
                "grid_position": safe(row.get("GridPosition"), int),
                "finish_position": safe(row.get("Position"), int),
                "status": safe(row.get("Status"), str, "Unknown"),
                "points": safe(row.get("Points"), float, 0),
                "laps_completed": safe(row.get("NumberOfLaps"), int, 0),
                "time": "",
                "fastest_lap_time": "",
                "fastest_lap_rank": None,
            })
        return {
            "results": sorted(output, key=lambda x: x["finish_position"] or 99),
            "source": "fastf1",
        }
    except Exception as e:
        logger.warning(f"FastF1 results fallback error: {e}")
        return {"results": [], "source": "none", "error": str(e)}


@app.get("/race/{year}/{round_number}/incidents")
def get_race_incidents(year: int, round_number: int):
    try:
        session = _get_fastf1_session(year, round_number)
        track_status = session.track_status
        if track_status is None or track_status.empty:
            return {"incidents": []}

        STATUS_MAP = {
            "1": "Track Clear", "2": "Yellow Flag", "4": "Safety Car",
            "5": "Red Flag", "6": "Virtual Safety Car", "7": "VSC Ending",
        }
        seen, unique = set(), []
        for _, row in track_status.iterrows():
            code = str(row.get("Status", ""))
            label = STATUS_MAP.get(code, f"Status {code}")
            if code not in ["1"] and label not in seen:
                seen.add(label)
                unique.append({"status": code, "label": label})
        return {"incidents": unique}
    except Exception as e:
        return {"incidents": [], "error": str(e)}


@app.get("/race/{year}/{round_number}/lap-positions")
def get_lap_positions(year: int, round_number: int):
    """Driver position on every lap for the lap chart.
    Returns driver_number (from FastF1, correct for this session) and 3-letter code."""
    try:
        session = _get_fastf1_session(year, round_number)
        laps = session.laps[["Driver", "DriverNumber", "LapNumber", "Position"]].copy()
        laps = laps.dropna(subset=["LapNumber", "Position"])
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["Position"] = laps["Position"].astype(int)
        laps["DriverNumber"] = laps["DriverNumber"].astype(int)
        return laps.to_dict(orient="records")
    except Exception as e:
        logger.warning(f"lap-positions error: {e}")
        return []


@app.get("/race/{year}/{round_number}/fastest-laps")
def get_fastest_laps(year: int, round_number: int):
    """Each driver's fastest lap. Uses FastF1 driver codes (correct for this season/race)."""
    try:
        session = _get_fastf1_session(year, round_number)
        laps = session.laps.copy()
        laps = laps.dropna(subset=["LapTime"])

        fastest = []
        for driver_num in laps["DriverNumber"].unique():
            driver_laps = laps[laps["DriverNumber"] == driver_num]
            if driver_laps.empty:
                continue
            best = driver_laps.loc[driver_laps["LapTime"].idxmin()]
            lap_time_s = (
                best["LapTime"].total_seconds()
                if hasattr(best["LapTime"], "total_seconds")
                else float(best["LapTime"])
            )
            mins = int(lap_time_s // 60)
            secs = lap_time_s % 60
            formatted = f"{mins}:{secs:06.3f}"

            speed_val = best.get("SpeedI1", None)
            try:
                speed = round(float(speed_val), 1) if speed_val is not None and not pd.isna(speed_val) else 0
            except Exception:
                speed = 0

            fastest.append({
                "driver_number": int(best["DriverNumber"]),
                "driver_code": str(best["Driver"]),
                "lap_number": int(best["LapNumber"]),
                "lap_time_seconds": round(lap_time_s, 3),
                "lap_time_formatted": formatted,
                "avg_speed_kph": speed,
                "tyre_compound": str(best.get("Compound", "UNKNOWN")),
            })

        fastest.sort(key=lambda x: x["lap_time_seconds"])
        for i, f in enumerate(fastest):
            f["rank"] = i + 1
        return fastest
    except Exception as e:
        logger.warning(f"fastest-laps error: {e}")
        return []


@app.get("/race/{year}/{round_number}/tyre-strategies")
def get_tyre_strategies(year: int, round_number: int):
    """Tyre stint data. Uses FastF1 driver numbers (correct for this session)."""
    try:
        session = _get_fastf1_session(year, round_number)
        laps = session.laps[["Driver", "DriverNumber", "LapNumber", "Compound", "Stint"]].copy()
        laps = laps.dropna(subset=["LapNumber", "Compound"])
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["DriverNumber"] = laps["DriverNumber"].astype(int)
        laps["Stint"] = laps["Stint"].astype(int)

        strategies: dict = {}
        for _, row in laps.iterrows():
            dnum = int(row["DriverNumber"])
            code = str(row["Driver"])
            if dnum not in strategies:
                strategies[dnum] = {"driver_number": dnum, "driver_code": code, "stints": {}}
            stint = int(row["Stint"])
            compound = str(row["Compound"])
            if stint not in strategies[dnum]["stints"]:
                strategies[dnum]["stints"][stint] = {"stint": stint, "compound": compound, "laps": []}
            strategies[dnum]["stints"][stint]["laps"].append(int(row["LapNumber"]))

        result = []
        for dnum, data in strategies.items():
            stints = []
            for stint_num in sorted(data["stints"].keys()):
                s = data["stints"][stint_num]
                lap_list = sorted(s["laps"])
                stints.append({
                    "stint": s["stint"],
                    "compound": s["compound"],
                    "start_lap": lap_list[0],
                    "end_lap": lap_list[-1],
                    "lap_count": len(lap_list),
                })
            result.append({
                "driver_number": dnum,
                "driver_code": data["driver_code"],
                "stints": stints,
            })

        return result
    except Exception as e:
        logger.warning(f"tyre-strategies error: {e}")
        return []


@app.get("/race/{year}/{round_number}/pit-stops")
def get_pit_stops(year: int, round_number: int):
    results = fetch_results_from_jolpica(year, round_number)

    def norm(s: str) -> str:
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()

    def resolve_abbr(driver_id: str) -> str:
        if not driver_id:
            return ""
        driver_id_clean = norm(driver_id.replace("_", ""))
        for res in results:
            abbr = res["abbreviation"]
            full = res["full_name"]
            surname = norm(full.split()[-1])
            firstname = norm(full.split()[0])
            full_norm = norm(full.replace(" ", ""))
            if (driver_id_clean == full_norm or
                driver_id_clean == firstname + surname or
                driver_id_clean == surname or
                norm(driver_id) == surname or
                norm(abbr) == norm(driver_id)):
                return abbr
        return ""

    # ── Try Jolpica ──────────────────────────────────────────────────────────
    try:
        r = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/{round_number}/pitstops.json?limit=100",
            timeout=10,
        )
        data = r.json()["MRData"]["RaceTable"]["Races"]
        if data and data[0].get("PitStops"):
            pit_stops = data[0]["PitStops"]

            result = []
            for p in pit_stops:
                driver_id = p.get("driverId", "")
                abbr = resolve_abbr(driver_id)
                
                # Get driver_number from results by abbreviation
                driver_num = 0
                for res in results:
                    if res["abbreviation"] == abbr:
                        driver_num = res["driver_number"]
                        break

                duration_s = None
                try:
                    duration_s = float(p.get("duration", "")) if p.get("duration") else None
                except Exception:
                    duration_s = None

                result.append({
                    "driver_number": driver_num,
                    "driver_id": driver_id,
                    "driver_code": abbr,  # now correctly populated
                    "stop_number": int(p.get("stop", 1)),
                    "lap": int(p.get("lap", 0)),
                    "time_of_day": p.get("time", ""),
                    "duration_seconds": duration_s,
                    "duration_formatted": p.get("duration", "—"),
                })

            # Deduplicate
            seen = set()
            deduped = []
            for p in result:
                key = (p["driver_id"], p["stop_number"], p["lap"])
                if key not in seen:
                    seen.add(key)
                    deduped.append(p)

            deduped.sort(key=lambda x: (x["lap"], x["duration_seconds"] or 99))
            return deduped
    except Exception as e:
        logger.warning(f"Jolpica pit stops error: {e}")

    # ── FastF1 fallback ───────────────────────────────────────────────────────
    try:
        session = _get_fastf1_session(year, round_number)
        laps = session.laps.copy()
        pit_laps = laps[laps["PitInTime"].notna()].copy()

        result = []
        stop_counter: dict = {}
        for _, row in pit_laps.sort_values("LapNumber").iterrows():
            dnum = int(row["DriverNumber"])
            code = str(row["Driver"])  # FastF1 3-letter code, reliable
            stop_counter[dnum] = stop_counter.get(dnum, 0) + 1

            pit_duration = None
            duration_fmt = "—"
            try:
                pit_out = laps[
                    (laps["DriverNumber"] == row["DriverNumber"]) &
                    (laps["LapNumber"] == row["LapNumber"] + 1) &
                    laps["PitOutTime"].notna()
                ]
                if not pit_out.empty:
                    dur = (pit_out.iloc[0]["PitOutTime"] - row["PitInTime"]).total_seconds()
                    if 0 < dur < 120:
                        pit_duration = round(dur, 3)
                        duration_fmt = f"{pit_duration:.3f}"
            except Exception:
                pass

            result.append({
                "driver_number": dnum,
                "driver_id": code,
                "driver_code": code,  # FastF1 code is reliable
                "stop_number": stop_counter[dnum],
                "lap": int(row["LapNumber"]),
                "time_of_day": "",
                "duration_seconds": pit_duration,
                "duration_formatted": duration_fmt,
            })

        result.sort(key=lambda x: (x["lap"], x["duration_seconds"] or 99))
        return result
    except Exception as e:
        logger.warning(f"FastF1 pit stops fallback error: {e}")
        return []

@app.post("/batch/process")
def run_batch_processor(year: int, round_number: int):
    def run():
        from spark_processing.batch_processor import process_historical_session
        process_historical_session(year=year, round_number=round_number)

    threading.Thread(target=run, daemon=True).start()
    return {
        "status": "started",
        "year": year,
        "round": round_number,
        "message": f"Processing {year} Round {round_number} in background. Data will appear in ~60 seconds.",
    }

@app.post("/strategy")
def get_strategy(situation: DriverSituation):
    try:
        from agents.strategy_agent import analyze_driver_situation
        result = analyze_driver_situation(**situation.model_dump())
        return {"driver_number": situation.driver_number, "recommendation": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/commentary")
def get_commentary(req: CommentaryRequest):
    try:
        from agents.commentary_agent import generate_lap_commentary
        result = generate_lap_commentary(**req.model_dump())
        return {"driver_number": req.driver_number, "commentary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/search")
def rag_search(query: str, top_k: int = 5):
    try:
        from agents.rag_agent import get_rag_context
        result = get_rag_context(query, top_k=top_k)
        return {"query": query, "context": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))