import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyspark.sql import functions as F
from loguru import logger
from logger_config import setup_logging

from config import settings
from spark_processing.spark_session import get_spark_session
from spark_processing.schemas import LAP_DATA_SCHEMA
from spark_processing.features import compute_all_features

setup_logging()


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
    spark = get_spark_session("F1LapProcessor")
    logger.info("Starting F1 Lap Processor streaming job...")

    raw_stream = create_lap_stream(spark)

    parsed_stream = parse_lap_messages(raw_stream)

    def process_batch(batch_df, batch_id):
        if batch_df.count() == 0:
            return

        logger.info(f"Processing batch {batch_id}: {batch_df.count()} laps")

        enriched_df = compute_all_features(batch_df)

        logger.info(f"Batch {batch_id} enriched features sample:")
        enriched_df.select(
            "driver_number",
            "lap_number",
            "lap_duration",
            "rolling_avg_lap_time",
            "lap_delta",
            "tyre_compound",
            "tyre_age_laps",
            "tyre_degradation_rate",
            "should_pit_soon",
            "estimated_laps_to_pit"
        ).orderBy("driver_number", "lap_number").show(10, truncate=False)

        # Write to in-memory table so agents can query it with SQL
        enriched_df.write \
            .mode("append") \
            .saveAsTable("f1_lap_features")

        # Write to parquet files as local warehouse
        output_path = "data/spark_output/lap_features"
        os.makedirs(output_path, exist_ok=True)
        enriched_df.write \
            .mode("append") \
            .partitionBy("driver_number") \
            .parquet(output_path)

        logger.info(
            f"Batch {batch_id} complete: wrote {enriched_df.count()} "
            f"enriched laps to warehouse"
        )

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