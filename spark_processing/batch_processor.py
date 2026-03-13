import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from loguru import logger
from logger_config import setup_logging
from pyspark.sql import functions as F

from config import settings
from spark_processing.spark_session import get_spark_session
from spark_processing.features import compute_all_features

setup_logging()


def process_historical_session(
    year: int,
    round_number: int,
    output_path: str = "data/spark_output/historical"
) -> pd.DataFrame:
    from data_ingestion.fastf1_connector import FastF1Connector

    logger.info(f"Processing historical session: {year} Round {round_number}")

    connector = FastF1Connector()
    session = connector.load_session(year, round_number, "R")
    laps = connector.get_laps(session)

    if not laps:
        logger.error("No laps found in session")
        return pd.DataFrame()

    laps_dicts = [lap.to_dict() for lap in laps]
    laps_df = pd.DataFrame(laps_dicts)

    spark = get_spark_session("F1BatchProcessor")
    spark_df = spark.createDataFrame(laps_df)

    logger.info(f"Loaded {spark_df.count()} laps into Spark")

    enriched_df = compute_all_features(spark_df)

    logger.info("Feature summary by driver:")
    enriched_df.groupBy("driver_number").agg(
        F.count("lap_number").alias("total_laps"),
        F.min("lap_duration").alias("fastest_lap"),
        F.avg("lap_duration").alias("avg_lap_time"),
        F.avg("tyre_degradation_rate").alias("avg_deg_rate"),
        F.max("stint_length").alias("longest_stint")
    ).orderBy("driver_number").show()

    save_path = f"{output_path}/{year}_round{round_number}"
    os.makedirs(save_path, exist_ok=True)
    enriched_df.write.mode("overwrite").partitionBy("driver_number").parquet(save_path)
    logger.success(f"Saved enriched features to {save_path}")

    result = enriched_df.toPandas()
    spark.stop()
    return result


if __name__ == "__main__":
    df = process_historical_session(
        year=settings.REPLAY_YEAR,
        round_number=settings.REPLAY_ROUND
    )
    print(f"\nTotal enriched laps: {len(df)}")
    print("\nSample enriched lap:")
    print(df[[
        "driver_number", "lap_number", "lap_duration",
        "rolling_avg_lap_time", "lap_delta",
        "tyre_degradation_rate", "should_pit_soon"
    ]].head(10).to_string())