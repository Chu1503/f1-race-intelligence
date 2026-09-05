import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyspark.sql import functions as F
from loguru import logger
from logger_config import setup_logging

from config import settings
from spark_processing.spark_session import get_spark_session
from spark_processing.schemas import LAP_DATA_SCHEMA
from spark_processing.pandas_features import compute_features_pandas
from pathlib import Path
import pandas as pd
import uuid

setup_logging()


def _atomic_parquet(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, destination)


def write_live_batch(batch_df) -> int:
    """Merge a micro-batch into a durable per-session snapshot.

    Recomputing over the accumulated race avoids resetting rolling windows at
    every Kafka micro-batch, which previously made live features misleading.
    """
    incoming = batch_df.toPandas()
    written = 0
    base = Path(settings.LIVE_OUTPUT_DIR)
    for session_key, session_batch in incoming.groupby("session_key"):
        session_dir = base / f"session_key={int(session_key)}"
        raw_path = session_dir / "raw.parquet"
        if raw_path.exists():
            raw = pd.concat([pd.read_parquet(raw_path), session_batch], ignore_index=True)
        else:
            raw = session_batch.copy()
        raw = raw.drop_duplicates(["driver_number", "lap_number"], keep="last")
        raw = raw.sort_values(["driver_number", "lap_number"])
        features = compute_features_pandas(raw)
        _atomic_parquet(raw, raw_path)
        _atomic_parquet(features, session_dir / "features.parquet")
        written += len(features)
    return written


def create_lap_stream(spark):
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", settings.KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", settings.KAFKA_LAP_DATA_TOPIC)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )


def parse_lap_messages(raw_stream):
    return (
        raw_stream
        .select(F.col("value").cast("string").alias("json_str"))
        .select(F.from_json(F.col("json_str"), LAP_DATA_SCHEMA).alias("data"))
        .select("data.*")
        .filter(F.col("driver_number").isNotNull())
        .filter(F.col("lap_number").isNotNull())
    )


def run_streaming_job():
    spark = get_spark_session("F1LapProcessor", with_kafka=True)
    logger.info("Starting F1 Lap Processor streaming job...")

    raw_stream = create_lap_stream(spark)

    parsed_stream = parse_lap_messages(raw_stream)

    def process_batch(batch_df, batch_id):
        if batch_df.count() == 0:
            return

        logger.info(f"Processing batch {batch_id}: {batch_df.count()} laps")

        feature_rows = write_live_batch(batch_df)
        logger.info(f"Batch {batch_id} complete: live snapshot now has {feature_rows} feature rows")

    query = (
        parsed_stream.writeStream
        .foreachBatch(process_batch)
        .option("checkpointLocation", "data/spark_checkpoints/lap_processor")
        .trigger(processingTime="5 seconds")
        .start()
    )

    logger.info("Lap processor streaming job started. Waiting for data...")
    logger.info("Press Ctrl+C to stop.")

    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        logger.info("Stopping lap processor...")
        query.stop()
        spark.stop()
        logger.info("Lap processor stopped cleanly.")


if __name__ == "__main__":
    run_streaming_job()
