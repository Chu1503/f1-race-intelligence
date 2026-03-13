import sys, os

os.environ["HADOOP_HOME"] = r"C:\hadoop"
os.environ["PATH"] = r"C:\hadoop\bin;" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from logger_config import setup_logging
setup_logging()

def test_spark_session():
    logger.info("\nTesting Spark Session")
    try:
        from spark_processing.spark_session import get_spark_session
        spark = get_spark_session("F1Test")
        version = spark.version
        logger.success(f"PASS: Spark session created. Version: {version}")
        spark.stop()
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        return False


def test_feature_engineering():
    logger.info("\nTesting Feature Engineering")
    try:
        from spark_processing.spark_session import get_spark_session
        from spark_processing.features import compute_all_features
        from spark_processing.schemas import LAP_DATA_SCHEMA

        spark = get_spark_session("F1FeatureTest")

        test_data = []
        for lap in range(1, 21):
            test_data.append((
                9999,
                1,
                lap,
                float(90.0 + (lap * 0.05)),
                float(28.0),
                float(32.0),
                float(30.0 + (lap * 0.05)),
                "SOFT",
                lap,
                False,
                False,
                "2024-01-01T00:00:00",
                "test"
            ))

        df = spark.createDataFrame(test_data, schema=LAP_DATA_SCHEMA)
        enriched = compute_all_features(df)

        count = enriched.count()
        logger.success(f"PASS: Feature engineering ran on {count} laps")

        expected_cols = [
            "rolling_avg_lap_time", "lap_delta",
            "tyre_degradation_rate", "should_pit_soon",
            "estimated_laps_to_pit", "stint_length"
        ]
        for col in expected_cols:
            if col in enriched.columns:
                logger.success(f"PASS: Column '{col}' present")
            else:
                logger.error(f"FAIL: Column '{col}' missing")
                return False

        enriched.select(
            "lap_number", "lap_duration", "rolling_avg_lap_time",
            "lap_delta", "tyre_degradation_rate", "should_pit_soon"
        ).show(5)

        spark.stop()
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_processor():
    logger.info("\nTesting Batch Processor (Bahrain 2024)")
    try:
        from spark_processing.batch_processor import process_historical_session
        from config import settings

        df = process_historical_session(
            year=settings.REPLAY_YEAR,
            round_number=settings.REPLAY_ROUND
        )

        if df.empty:
            logger.error("FAIL: No data returned")
            return False

        logger.success(f"PASS: Processed {len(df)} laps with features")

        ver = df[df["driver_number"] == 1]
        if not ver.empty:
            logger.info(f"  Verstappen: {len(ver)} laps processed")
            logger.info(f"  Fastest lap: {ver['lap_duration'].min():.3f}s")
            logger.info(f"  Avg degradation rate: {ver['tyre_degradation_rate'].mean():.4f}s/lap")
            logger.info(f"  Laps flagged should_pit_soon: {ver['should_pit_soon'].sum()}")

        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("Spark Processing Tests")

    results = {
        "Spark session": test_spark_session(),
        "Feature engineering": test_feature_engineering(),
        "Batch processor": test_batch_processor(),
    }

    passed = sum(results.values())
    for name, ok in results.items():
        logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}")
    logger.info(f"\n{passed}/3 tests passed")

    if passed == 3:
        logger.success("Spark feature pipeline working!")
    return passed == 3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)