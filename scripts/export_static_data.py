"""Export completed race data as cacheable frontend assets.

Run this after historical processing and before deploying the frontend:

    python scripts/export_static_data.py

The manifest is mutable and short-cached. Race bundles are content-addressed, so
they can be cached indefinitely by browsers and the CDN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api import main as api  # noqa: E402


OUTPUT_ROOT = PROJECT_ROOT / "frontend" / "public" / "data"
RACE_ROOT = OUTPUT_ROOT / "races"


def normalize_json(value: Any) -> Any:
    """Convert Pandas/NumPy values and non-finite floats to strict JSON."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): normalize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json(item) for item in value]
    if hasattr(value, "item"):
        return normalize_json(value.item())
    return str(value)


def encode_json(value: Any) -> bytes:
    return json.dumps(
        normalize_json(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def call_with_retry(label: str, operation: Callable[[], Any], attempts: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # providers expose several exception types
            last_error = exc
            print(f"[retry {attempt}/{attempts}] {label}: {exc}")
    assert last_error is not None
    raise last_error


def build_race_bundle(year: int, round_number: int) -> dict[str, Any]:
    results_response = call_with_retry(
        f"{year} round {round_number} results",
        lambda: api.get_race_results(year, round_number),
    )
    return {
        "version": 1,
        "year": year,
        "round": round_number,
        "laps": api.get_all_laps(year, round_number),
        "driverStats": api.get_race_drivers(year, round_number),
        "results": results_response.get("results", []),
        "resultsSource": results_response.get("source", "none"),
        "incidents": api.get_race_incidents(year, round_number).get("incidents", []),
        "lapPositions": api.get_lap_positions(year, round_number),
        "fastestLaps": api.get_fastest_laps(year, round_number),
        "tyreStrategies": api.get_tyre_strategies(year, round_number),
        "pitStops": call_with_retry(
            f"{year} round {round_number} pit stops",
            lambda: api.get_pit_stops(year, round_number),
        ),
    }


def read_previous_manifest() -> dict[str, Any]:
    path = OUTPUT_ROOT / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def export_static_data(force: bool = False) -> dict[str, Any]:
    available = api.get_available_races()["races"]
    seasons = api.get_seasons()["seasons"]
    available_years = {race["year"] for race in available}
    previous_race_files = read_previous_manifest().get("raceFiles", {})

    years: dict[str, dict[str, Any]] = {}
    for year in seasons:
        try:
            calendar = call_with_retry(
                f"{year} calendar", lambda year=year: api.fetch_calendar_for_year(year)
            )
        except Exception as exc:
            print(f"[warning] no static calendar for {year}: {exc}")
            calendar = []
        drivers: list[dict[str, Any]] = []
        if year in available_years:
            drivers = call_with_retry(
                f"{year} drivers", lambda year=year: api.fetch_drivers_for_year(year)
            )
        years[str(year)] = {"calendar": calendar, "drivers": drivers}

    race_files: dict[str, str] = {}
    total_raw_bytes = 0
    for index, race in enumerate(sorted(available, key=lambda item: (item["year"], item["round"])), 1):
        year, round_number = race["year"], race["round"]
        race_key = f"{year}-{round_number}"
        previous_path = previous_race_files.get(race_key)
        if not force and isinstance(previous_path, str):
            existing_path = PROJECT_ROOT / "frontend" / "public" / previous_path.lstrip("/")
            if existing_path.exists():
                print(f"[{index}/{len(available)}] reusing {year} round {round_number}")
                race_files[race_key] = previous_path
                total_raw_bytes += existing_path.stat().st_size
                continue
        print(f"[{index}/{len(available)}] exporting {year} round {round_number}")
        encoded = encode_json(build_race_bundle(year, round_number))
        digest = hashlib.sha256(encoded).hexdigest()[:12]
        relative_path = Path("races") / str(year) / f"{round_number}.{digest}.json"
        output_path = OUTPUT_ROOT / relative_path
        write_atomic(output_path, encoded)
        for stale_path in output_path.parent.glob(f"{round_number}.*.json"):
            if stale_path != output_path:
                stale_path.unlink()
        race_files[race_key] = f"/data/{relative_path.as_posix()}"
        total_raw_bytes += len(encoded)

    manifest = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "seasons": seasons,
        "availableRaces": available,
        "years": years,
        "raceFiles": race_files,
    }
    write_atomic(OUTPUT_ROOT / "manifest.json", encode_json(manifest))
    print(
        f"Exported {len(available)} races ({total_raw_bytes:,} raw bytes) "
        f"and {len(years)} season catalogs."
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Export frontend historical data")
    parser.add_argument("--force", action="store_true", help="Rebuild existing bundles")
    args = parser.parse_args()
    export_static_data(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
