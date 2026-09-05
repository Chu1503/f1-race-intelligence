from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from loguru import logger

from config import settings
from logger_config import setup_logging
from spark_processing.pandas_features import compute_features_pandas

setup_logging()


def process_historical_session(
    year: int,
    round_number: int,
    output_path: str | None = None,
) -> pd.DataFrame:
    """Fetch, enrich, and atomically publish one historical race."""
    from data_ingestion.fastf1_connector import FastF1Connector

    if not 1950 <= year <= 2100 or not 1 <= round_number <= 30:
        raise ValueError("year or round_number is outside the supported range")

    logger.info(f"Processing historical session: {year} Round {round_number}")
    connector = FastF1Connector()
    session = connector.load_session(year, round_number, "R")
    laps = connector.get_laps(session)
    if not laps:
        raise RuntimeError("FastF1 returned no completed laps for this race")

    enriched = compute_features_pandas(pd.DataFrame(lap.to_dict() for lap in laps))
    if enriched.empty:
        raise RuntimeError("All downloaded laps failed feature-quality validation")

    base = Path(output_path or settings.DATA_DIR / "spark_output" / "historical").resolve()
    base.mkdir(parents=True, exist_ok=True)
    destination = (base / f"{year}_round{round_number}").resolve()
    if base not in destination.parents:
        raise ValueError("Refusing to write outside the historical data directory")
    if destination.exists():
        raise FileExistsError(f"Race data already exists at {destination}")

    staging = base / f".{destination.name}.tmp-{uuid.uuid4().hex}"
    try:
        enriched.to_parquet(staging, partition_cols=["driver_number"], index=False)
        (staging / "_SUCCESS").write_text("ok\n", encoding="utf-8")
        staging.rename(destination)
    except Exception:
        if staging.exists():
            import shutil
            shutil.rmtree(staging)
        raise

    logger.success(f"Saved {len(enriched)} enriched laps to {destination}")
    return enriched


if __name__ == "__main__":
    frame = process_historical_session(settings.REPLAY_YEAR, settings.REPLAY_ROUND)
    print(f"Total enriched laps: {len(frame)}")
