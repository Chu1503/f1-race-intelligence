import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import threading
import time
import requests
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from loguru import logger
from logger_config import setup_logging
from datetime import datetime
import unicodedata
from pathlib import Path

from api.jobs import job_manager
from api.security import rate_limit, require_service_key
from config import settings

setup_logging()


class DataProviderError(RuntimeError):
    pass

app = FastAPI(title="F1 Race Intelligence API", version="1.0.0")


@app.middleware("http")
async def development_request_timing(request: Request, call_next):
    if settings.ENVIRONMENT == "production":
        return await call_next(request)
    started = time.perf_counter()
    try:
        return await call_next(request)
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1_000
        logger.info(f"[perf] api {request.method} {request.url.path} {elapsed_ms:.1f}ms")


@app.exception_handler(DataProviderError)
async def provider_error_handler(_request, exc: DataProviderError):
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": "provider_unavailable"})

_extra_origin = os.getenv("FRONTEND_URL", "").strip()
_allow_origins = [
    "http://localhost:3000",
    "https://f1-race-intelligence.vercel.app",
]
if _extra_origin:
    _allow_origins.append(_extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
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
_laps_cache: dict = {}   # (year, round) -> list[dict]
_feature_frame_cache: dict[tuple[int, int], pd.DataFrame] = {}

LAP_RESPONSE_COLUMNS = (
    "driver_number",
    "lap_number",
    "lap_duration",
    "tyre_compound",
    "tyre_age_laps",
    "tyre_degradation_rate",
    "rolling_avg_lap_time",
    "lap_delta",
    "should_pit_soon",
    "estimated_laps_to_pit",
    "stint_length",
)


def _load_race_frame(year: int, round_number: int) -> pd.DataFrame:
    key = (year, round_number)
    if key in _feature_frame_cache:
        return _feature_frame_cache[key].copy()
    race_folder = f"{year}_round{round_number}"
    persistent = settings.DATA_DIR / "spark_output" / "historical" / race_folder
    packaged = settings.PROJECT_ROOT / "data" / "spark_output" / "historical" / race_folder
    path = next((candidate for candidate in (persistent, packaged) if candidate.exists()), None)
    if path is None:
        raise HTTPException(status_code=404, detail="No processed race data found.")
    from spark_processing.pandas_features import compute_features_pandas
    frame = compute_features_pandas(pd.read_parquet(path))
    _feature_frame_cache[key] = frame
    return frame.copy()

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
        r.raise_for_status()
        drivers_raw = r.json()["MRData"]["DriverTable"]["Drivers"]

        standings_r = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/driverStandings.json", timeout=10
        )
        standings_r.raise_for_status()
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
        raise DataProviderError(f"Driver data provider is unavailable for {year}.") from e


def fetch_calendar_for_year(year: int) -> list:
    if year in _calendar_cache:
        return _calendar_cache[year]
    cached = _disk_cache_read(f"calendar_{year}")
    if cached is not None:
        _calendar_cache[year] = cached
        return cached
    try:
        r = requests.get(f"https://api.jolpi.ca/ergast/f1/{year}.json", timeout=10)
        r.raise_for_status()
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
        raise DataProviderError(f"Calendar provider is unavailable for {year}.") from e


def fetch_results_from_jolpica(year: int, round_number: int) -> list:
    cache_key = f"{year}_{round_number}"
    if cache_key in _results_cache:
        return _results_cache[cache_key]
    try:
        r = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/{round_number}/results.json",
            timeout=10,
        )
        r.raise_for_status()
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
                "driver_number": int(res.get("number", driver.get("permanentNumber", 0))),
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
        raise DataProviderError(f"Results provider is unavailable for {year} round {round_number}.") from e


_fastf1_session_cache: dict[tuple[int, int], object] = {}
_fastf1_session_lock = threading.Lock()


def _get_fastf1_session(year: int, round_number: int):
    """Load a FastF1 session with caching."""
    key = (year, round_number)
    if key in _fastf1_session_cache:
        return _fastf1_session_cache[key]
    with _fastf1_session_lock:
        if key in _fastf1_session_cache:
            return _fastf1_session_cache[key]
        import fastf1, warnings
        warnings.filterwarnings("ignore")
        settings.FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(settings.FASTF1_CACHE_DIR))
        session = fastf1.get_session(year, round_number, "R")
        session.load(telemetry=False, weather=False, messages=False)
        if len(_fastf1_session_cache) >= 12:
            _fastf1_session_cache.pop(next(iter(_fastf1_session_cache)))
        _fastf1_session_cache[key] = session
        return session


class DriverSituation(BaseModel):
    driver_number: int = Field(ge=1, le=999)
    lap_number: int = Field(ge=1, le=200)
    lap_duration: float = Field(gt=0, le=600)
    tyre_compound: str = Field(min_length=1, max_length=32)
    tyre_age_laps: int = Field(ge=0, le=200)
    tyre_degradation_rate: Optional[float] = 0.0
    rolling_avg_lap_time: Optional[float] = None
    lap_delta: Optional[float] = None
    should_pit_soon: bool
    estimated_laps_to_pit: Optional[float] = 999.0
    position: Optional[int] = None
    gap_to_leader: Optional[float] = None
    circuit_name: str = "unknown"
    total_race_laps: int = Field(default=57, ge=1, le=200)


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


class ProcessingRequest(BaseModel):
    year: int = Field(ge=1950, le=2100)
    round_number: int = Field(ge=1, le=30)



@app.get("/")
def root():
    return {"status": "online", "service": "F1 Race Intelligence API"}


@app.get("/health")
def health():
    historical = settings.PROJECT_ROOT / "data" / "spark_output" / "historical"
    persistent_historical = settings.DATA_DIR / "spark_output" / "historical"
    checks = {
        "historical_data": any(root.exists() and any(root.glob("*_round*")) for root in {historical, persistent_historical}),
        "job_store": settings.JOB_DB_PATH.parent.exists(),
        "service_auth": bool(settings.SERVICE_API_KEY) or settings.ENVIRONMENT != "production",
        "anthropic_configured": bool(settings.ANTHROPIC_API_KEY),
        "rag_configured": bool(settings.PINECONE_API_KEY and settings.VOYAGE_API_KEY),
    }
    required = ("historical_data", "job_store", "service_auth")
    ready = all(checks[name] for name in required)
    return {"status": "healthy" if ready else "degraded", "ready": ready, "checks": checks}


@app.get("/health/ready")
def readiness():
    report = health()
    if not report["ready"]:
        raise HTTPException(status_code=503, detail=report)
    return report


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
    roots = {
        settings.PROJECT_ROOT / "data" / "spark_output" / "historical",
        settings.DATA_DIR / "spark_output" / "historical",
    }
    races_by_key = {}
    for base in roots:
        if not base.exists():
            continue
        for folder in base.iterdir():
            match = re.fullmatch(r"(\d{4})_round(\d+)", folder.name)
            if match and folder.is_dir() and (folder / "_SUCCESS").exists() and next(folder.rglob("*.parquet"), None):
                key = (int(match.group(1)), int(match.group(2)))
                races_by_key[key] = {"year": key[0], "round": key[1]}
    races = list(races_by_key.values())
    return {"races": sorted(races, key=lambda x: (x["year"], x["round"]), reverse=True)}


@app.get("/live/sessions")
def get_live_sessions():
    base = Path(settings.LIVE_OUTPUT_DIR)
    sessions = []
    if base.exists():
        for folder in base.glob("session_key=*"):
            features = folder / "features.parquet"
            if features.exists():
                sessions.append({
                    "session_key": int(folder.name.split("=", 1)[1]),
                    "updated_at": datetime.fromtimestamp(features.stat().st_mtime).isoformat(),
                })
    return {"mode": "live" if sessions else "historical", "sessions": sorted(sessions, key=lambda item: item["session_key"], reverse=True)}


@app.get("/live/sessions/{session_key}/laps")
def get_live_laps(session_key: int):
    path = Path(settings.LIVE_OUTPUT_DIR) / f"session_key={session_key}" / "features.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No processed live snapshot exists for that session.")
    frame = pd.read_parquet(path).replace({float("nan"): None, float("inf"): None, float("-inf"): None})
    return {"session_key": session_key, "laps": frame.to_dict(orient="records")}


@app.get("/race/{year}/{round_number}/laps")
def get_all_laps(year: int, round_number: int):
    key = (year, round_number)
    if key in _laps_cache:
        return _laps_cache[key]
    try:
        df = _load_race_frame(year, round_number)
        df = df.loc[:, [column for column in LAP_RESPONSE_COLUMNS if column in df.columns]]
        df = df.replace({float("nan"): None, float("inf"): None, float("-inf"): None})
        records = df.to_dict(orient="records")
        _laps_cache[key] = records
        return records
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/race/{year}/{round_number}/drivers")
def get_race_drivers(year: int, round_number: int):
    try:
        df = _load_race_frame(year, round_number)
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
    """Driver position on every lap. Uses FastF1 if cache available, else derives
    approximate positions from cumulative lap times in parquet."""
    # ── Try FastF1 first (exact telemetry positions) ──────────────────────────
    try:
        session = _get_fastf1_session(year, round_number)
        laps = session.laps[["Driver", "DriverNumber", "LapNumber", "Position"]].copy()
        laps = laps.dropna(subset=["LapNumber", "Position"])
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["Position"] = laps["Position"].astype(int)
        laps["DriverNumber"] = laps["DriverNumber"].astype(int)
        result = laps.to_dict(orient="records")
        if result:
            return result
    except Exception:
        pass

    # ── Fallback: derive from cumulative lap times in parquet ─────────────────
    try:
        df = _load_race_frame(year, round_number)
        df = df[["driver_number", "lap_number", "lap_duration"]].copy()
        df = df[df["lap_duration"] > 0].sort_values(["driver_number", "lap_number"])

        # Get driver_number → abbreviation map from Jolpica
        results = fetch_results_from_jolpica(year, round_number)
        num_to_code = {r["driver_number"]: r["abbreviation"] for r in results}

        # Compute cumulative race time per driver (approximation — excludes pit stop time)
        df["cum_time"] = df.groupby("driver_number")["lap_duration"].cumsum()

        positions = []
        for lap_num in sorted(df["lap_number"].unique()):
            lap_data = df[df["lap_number"] == lap_num].sort_values("cum_time")
            for pos, (_, row) in enumerate(lap_data.iterrows(), 1):
                dnum = int(row["driver_number"])
                positions.append({
                    "Driver": num_to_code.get(dnum, str(dnum)),
                    "DriverNumber": dnum,
                    "LapNumber": int(lap_num),
                    "Position": pos,
                })
        return positions
    except Exception as e:
        logger.warning(f"lap-positions fallback error: {e}")
        return []


@app.get("/race/{year}/{round_number}/fastest-laps")
def get_fastest_laps(year: int, round_number: int):
    """Each driver's fastest lap — built from parquet, no FastF1 needed."""
    try:
        df = _load_race_frame(year, round_number)
        # parquet already filters 60 < lap_duration < 200 — all laps are valid race laps
        df = df[df["lap_duration"] > 0]

        # Get driver_number → abbreviation map from Jolpica
        results = fetch_results_from_jolpica(year, round_number)
        num_to_code = {r["driver_number"]: r["abbreviation"] for r in results}

        fastest = []
        for dnum in df["driver_number"].unique():
            dnum_int = int(dnum)
            driver_laps = df[df["driver_number"] == dnum_int]
            if driver_laps.empty:
                continue
            best = driver_laps.loc[driver_laps["lap_duration"].idxmin()]

            lap_time_s = float(best["lap_duration"])
            mins = int(lap_time_s // 60)
            secs = lap_time_s % 60
            formatted = f"{mins}:{secs:06.3f}"

            compound = best.get("tyre_compound", "UNKNOWN")
            if pd.isna(compound):
                compound = "UNKNOWN"

            fastest.append({
                "driver_number": dnum_int,
                "driver_code": num_to_code.get(dnum_int, str(dnum_int)),
                "lap_number": int(best["lap_number"]),
                "lap_time_seconds": round(lap_time_s, 3),
                "lap_time_formatted": formatted,
                "avg_speed_kph": 0,
                "tyre_compound": str(compound),
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
    """Tyre stint data — built from parquet (stint_number column), no FastF1 needed."""
    try:
        df = _load_race_frame(year, round_number)
        df = df.sort_values(["driver_number", "lap_number"])

        # Get driver_number → abbreviation map from Jolpica
        results = fetch_results_from_jolpica(year, round_number)
        num_to_code = {r["driver_number"]: r["abbreviation"] for r in results}

        result = []
        for dnum in sorted(df["driver_number"].unique()):
            dnum_int = int(dnum)
            driver_laps = df[df["driver_number"] == dnum_int]
            code = num_to_code.get(dnum_int, str(dnum_int))

            stints = []
            # Group by stint_number (computed by Spark from tyre_age_laps resets)
            for stint_num in sorted(driver_laps["stint_number"].unique()):
                stint_laps = driver_laps[driver_laps["stint_number"] == stint_num]
                if stint_laps.empty:
                    continue
                # Most common compound in this stint (handles null rows)
                compound_series = stint_laps["tyre_compound"].dropna()
                compound = str(compound_series.mode().iloc[0]) if not compound_series.empty else "UNKNOWN"
                lap_nums = sorted(stint_laps["lap_number"].tolist())
                stints.append({
                    "stint": int(stint_num) + 1,  # stint_number is 0-indexed in parquet
                    "compound": compound,
                    "start_lap": lap_nums[0],
                    "end_lap": lap_nums[-1],
                    "lap_count": len(lap_nums),
                })

            if stints:
                result.append({
                    "driver_number": dnum_int,
                    "driver_code": code,
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
                    "source": "jolpica",
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
                "source": "fastf1_estimate",
            })

        result.sort(key=lambda x: (x["lap"], x["duration_seconds"] or 99))
        return result
    except Exception as e:
        logger.warning(f"FastF1 pit stops fallback error: {e}")
        return []

@app.post(
    "/processing/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_service_key), Depends(rate_limit("processing", limit=5, window_seconds=300))],
)
def create_processing_job(request: ProcessingRequest):
    race_folder = f"{request.year}_round{request.round_number}"
    destinations = [
        settings.DATA_DIR / "spark_output" / "historical" / race_folder,
        settings.PROJECT_ROOT / "data" / "spark_output" / "historical" / race_folder,
    ]
    if any(destination.exists() for destination in destinations):
        raise HTTPException(status_code=409, detail="That race is already available.")
    return job_manager.create(request.year, request.round_number)


@app.get(
    "/processing/jobs/{job_id}",
    dependencies=[Depends(require_service_key), Depends(rate_limit("job-status", limit=120))],
)
def get_processing_job(job_id: str):
    try:
        return job_manager.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Processing job not found.")


@app.post("/batch/process", status_code=status.HTTP_202_ACCEPTED, deprecated=True, dependencies=[Depends(require_service_key)])
def run_batch_processor(year: int = Query(ge=1950, le=2100), round_number: int = Query(ge=1, le=30)):
    """Compatibility alias for older clients; returns the tracked job object."""
    return create_processing_job(ProcessingRequest(year=year, round_number=round_number))

@app.post("/strategy", dependencies=[Depends(require_service_key), Depends(rate_limit("strategy", limit=10))])
def get_strategy(situation: DriverSituation):
    try:
        from agents.strategy_agent import analyze_driver_situation_detailed
        result = analyze_driver_situation_detailed(**situation.model_dump())
        return {"driver_number": situation.driver_number, **result}
    except Exception as e:
        logger.exception(f"Strategy generation failed: {e}")
        raise HTTPException(status_code=502, detail="Strategy generation is temporarily unavailable.")


@app.post("/commentary", dependencies=[Depends(require_service_key), Depends(rate_limit("commentary", limit=20))])
def get_commentary(req: CommentaryRequest):
    try:
        from agents.commentary_agent import generate_lap_commentary
        result = generate_lap_commentary(**req.model_dump())
        return {"driver_number": req.driver_number, "commentary": result}
    except Exception as e:
        logger.exception(f"Commentary generation failed: {e}")
        raise HTTPException(status_code=502, detail="Commentary generation is temporarily unavailable.")


@app.get("/rag/search", dependencies=[Depends(require_service_key), Depends(rate_limit("rag", limit=30))])
def rag_search(query: str = Query(min_length=3, max_length=500), top_k: int = Query(default=5, ge=1, le=20)):
    try:
        from agents.rag_agent import get_rag_context
        result = get_rag_context(query, top_k=top_k)
        return {"query": query, "context": result}
    except Exception as e:
        logger.exception(f"RAG search failed: {e}")
        raise HTTPException(status_code=502, detail="Historical retrieval is temporarily unavailable.")
