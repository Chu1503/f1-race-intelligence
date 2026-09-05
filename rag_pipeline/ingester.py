from __future__ import annotations

import math
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from loguru import logger

from logger_config import setup_logging
from rag_pipeline.embedder import embed_batch
from rag_pipeline.vector_store import upsert_vectors
from spark_processing.pandas_features import compute_features_pandas

setup_logging()


def clean(value: Any, default: Any = 0) -> Any:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return value
    except Exception:
        return default


def lap_to_document(
    row: pd.Series,
    year: int,
    round_number: int,
    circuit_name: str,
    outcome: dict[str, Any],
    next_stop: dict[str, Any],
) -> str:
    finish = outcome.get("finish_position") or "unclassified"
    status = outcome.get("status") or "unknown"
    next_pit = next_stop.get("lap")
    if next_pit:
        strategy_outcome = f"The driver next pitted on lap {next_pit} for {next_stop.get('compound', 'unknown')} tyres"
    else:
        strategy_outcome = "No later tyre change is recorded"
    return (
        f"{circuit_name}; {year} R{round_number}; driver {int(row['driver_number'])}; lap {int(row['lap_number'])}; "
        f"{row.get('tyre_compound', 'unknown')} age {int(clean(row.get('tyre_age_laps'), 0))}; "
        f"time {float(row['lap_duration']):.3f}s; avg {float(clean(row.get('rolling_avg_lap_time'), row['lap_duration'])):.3f}s; "
        f"degradation {float(clean(row.get('tyre_degradation_rate'), 0)):.4f}s/lap. "
        f"{strategy_outcome}. Result P{finish}, {status}, {float(outcome.get('points') or 0):g} points."
    )


def _next_stops(df: pd.DataFrame) -> dict[tuple[int, int], dict[str, Any]]:
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for driver_number, driver_laps in df.groupby("driver_number"):
        stints = (
            driver_laps.sort_values("lap_number")
            .groupby("stint_number", as_index=False)
            .agg(lap=("lap_number", "min"), compound=("tyre_compound", "first"))
            .sort_values("stint_number")
            .to_dict("records")
        )
        for index, stint in enumerate(stints):
            following = stints[index + 1] if index + 1 < len(stints) else {}
            result[(int(driver_number), int(stint["stint_number"]))] = following
    return result


def ingest_historical_session(
    parquet_path: str,
    year: int,
    round_number: int,
    circuit_name: str,
    outcomes: dict[int, dict[str, Any]] | None = None,
) -> int:
    if not circuit_name or circuit_name.lower() == "unknown":
        raise ValueError("A real circuit name is required for RAG ingestion")
    df = compute_features_pandas(pd.read_parquet(parquet_path)).sort_values(["driver_number", "lap_number"])
    if df.empty:
        raise ValueError(f"No laps found in {parquet_path}")
    if "stint_number" not in df:
        raise ValueError("Feature data must include stint_number before RAG ingestion")

    outcomes = outcomes or {}
    next_stops = _next_stops(df)
    # One midpoint per stint covers every race without indexing near-duplicates.
    samples = []
    for _, stint_laps in df.groupby(["driver_number", "stint_number"], sort=False):
        samples.append(stint_laps.iloc[[len(stint_laps) // 2]])
    df = pd.concat(samples, ignore_index=True)
    documents: list[str] = []
    rows = list(df.iterrows())
    for _, row in rows:
        driver = int(row["driver_number"])
        next_stop = next_stops.get((driver, int(row["stint_number"])), {})
        documents.append(lap_to_document(row, year, round_number, circuit_name, outcomes.get(driver, {}), next_stop))

    embeddings = embed_batch(documents)
    vectors = []
    for index, (_, row) in enumerate(rows):
        driver = int(row["driver_number"])
        outcome = outcomes.get(driver, {})
        next_stop = next_stops.get((driver, int(row["stint_number"])), {})
        outcome_summary = f"P{outcome.get('finish_position') or '?'}; {outcome.get('status') or 'unknown'}"
        vectors.append({
            "id": f"{year}_r{round_number}_d{driver}_l{int(row['lap_number'])}",
            "values": embeddings[index],
            "metadata": {
                "year": year,
                "round_number": round_number,
                "circuit": circuit_name,
                "driver_number": driver,
                "lap_number": int(row["lap_number"]),
                "lap_duration": float(clean(row.get("lap_duration"), 0)),
                "tyre_compound": str(clean(row.get("tyre_compound"), "UNKNOWN")),
                "tyre_age_laps": int(clean(row.get("tyre_age_laps"), 0)),
                "tyre_degradation_rate": float(clean(row.get("tyre_degradation_rate"), 0)),
                "stint_number": int(clean(row.get("stint_number"), 0)),
                "next_pit_lap": int(clean(next_stop.get("lap"), -1)),
                "next_compound": str(clean(next_stop.get("compound"), "NONE")),
                "finish_position": int(clean(outcome.get("finish_position"), -1)),
                "race_status": str(clean(outcome.get("status"), "unknown")),
                "outcome_summary": outcome_summary,
                "document": documents[index],
            },
        })

    total = upsert_vectors(vectors)
    logger.success(f"Ingested {total} outcome-aware vectors for {circuit_name}")
    return total
