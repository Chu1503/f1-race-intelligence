"""Rebuild the versioned, outcome-aware Pinecone corpus from local race data."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import requests
import time

from rag_pipeline.ingester import ingest_historical_session
from rag_pipeline.vector_store import get_index_stats


def fetch_race_context(year: int, round_number: int) -> tuple[str, dict[int, dict]]:
    response = requests.get(
        f"https://api.jolpi.ca/ergast/f1/{year}/{round_number}/results.json",
        timeout=30,
    )
    response.raise_for_status()
    races = response.json()["MRData"]["RaceTable"]["Races"]
    if not races:
        raise RuntimeError(f"No Jolpica results for {year} round {round_number}")
    race = races[0]
    circuit = race["Circuit"]["circuitName"]
    outcomes: dict[int, dict] = {}
    for result in race.get("Results", []):
        number = int(result.get("number") or result["Driver"].get("permanentNumber") or 0)
        outcomes[number] = {
            "finish_position": int(result.get("position") or 0) or None,
            "status": result.get("status", "unknown"),
            "points": float(result.get("points") or 0),
        }
    return circuit, outcomes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, help="Only rebuild one season")
    args = parser.parse_args()

    base = Path("data/spark_output/historical")
    total = 0
    races = 0
    for folder in sorted(base.iterdir()):
        match = re.fullmatch(r"(\d{4})_round(\d+)", folder.name)
        if not match or not (folder / "_SUCCESS").exists():
            continue
        year, round_number = map(int, match.groups())
        if args.year and year != args.year:
            continue
        circuit, outcomes = fetch_race_context(year, round_number)
        print(f"Ingesting {year} R{round_number}: {circuit}")
        total += ingest_historical_session(str(folder), year, round_number, circuit, outcomes)
        races += 1
        time.sleep(float(os.getenv("VOYAGE_RACE_INTERVAL_SECONDS", "31")))

    stats = get_index_stats()
    print(f"Indexed {total} laps from {races} races")
    print(stats)


if __name__ == "__main__":
    main()
