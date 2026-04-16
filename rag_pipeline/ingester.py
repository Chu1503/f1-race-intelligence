import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from loguru import logger
from logger_config import setup_logging

from rag_pipeline.embedder import embed_batch
from rag_pipeline.vector_store import upsert_vectors

setup_logging()


def lap_to_document(row: pd.Series, year: int, round_number: int) -> str:
    pit_flag = "should pit soon" if row.get("should_pit_soon") else "pit not needed yet"
    return (
        f"Driver {int(row['driver_number'])} in {year} Round {round_number}: "
        f"Lap {int(row['lap_number'])}, "
        f"lap time {row['lap_duration']:.3f}s on {row.get('tyre_compound', 'unknown')} tyres "
        f"(age {int(row.get('tyre_age_laps', 0))} laps). "
        f"Rolling avg {row.get('rolling_avg_lap_time', 0):.3f}s, "
        f"delta to personal best +{row.get('lap_delta', 0):.3f}s. "
        f"Tyre degradation rate {row.get('tyre_degradation_rate', 0):.4f}s/lap. "
        f"Stint length {int(row.get('stint_length', 0))} laps. "
        f"Strategy assessment: {pit_flag}."
    )

def clean(val, default=0):
    try:
        if val is None:
            return default
        import math
        if isinstance(val, float) and math.isnan(val):
            return default
        return val
    except Exception:
        return default

def ingest_historical_session(
    parquet_path: str,
    year: int,
    round_number: int,
    circuit_name: str = "unknown"
) -> int:
    logger.info(f"Loading parquet from {parquet_path}")
    df = pd.read_parquet(parquet_path)
    logger.info(f"Loaded {len(df)} laps from {year} Round {round_number}")

    documents = []
    for _, row in df.iterrows():
        doc = lap_to_document(row, year, round_number)
        documents.append(doc)

    logger.info(f"Embedding {len(documents)} documents...")
    embeddings = embed_batch(documents)

    vectors = []
    for i, (_, row) in enumerate(df.iterrows()):
        vector_id = f"{year}_r{round_number}_d{int(row['driver_number'])}_l{int(row['lap_number'])}"
        vectors.append({
            "id": vector_id,
            "values": embeddings[i],
            "metadata": {
                "year": year,
                "round_number": round_number,
                "circuit": circuit_name,
                "driver_number": int(clean(row.get("driver_number"), 0)),
                "lap_number": int(clean(row.get("lap_number"), 0)),
                "lap_duration": float(clean(row.get("lap_duration"), 0)),
                "tyre_compound": str(row.get("tyre_compound", "unknown")),
                "tyre_age_laps": int(clean(row.get("tyre_age_laps"), 0)),
                "tyre_degradation_rate": float(clean(row.get("tyre_degradation_rate"), 0)),
                "should_pit_soon": bool(row.get("should_pit_soon", False)),
                "stint_length": int(clean(row.get("stint_length"), 0)),
                "document": documents[i]
            }
        })

    total = upsert_vectors(vectors)
    logger.success(f"Ingested {total} vectors for {year} Round {round_number}")
    return total