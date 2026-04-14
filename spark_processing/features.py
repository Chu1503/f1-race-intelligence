from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import FloatType


def add_rolling_avg_lap_time(df: DataFrame, window_size: int = 5) -> DataFrame:
    """
    Compute rolling average lap time over the last N laps per driver.
    """
    window = (
        Window
        .partitionBy("driver_number")
        .orderBy("lap_number")
        .rowsBetween(-window_size + 1, 0)
    )
    return df.withColumn(
        "rolling_avg_lap_time",
        F.avg("lap_duration").over(window)
    )


def add_lap_delta(df: DataFrame) -> DataFrame:
    """
    Compute each lap's time relative to the driver's personal best in the race.
    """
    window = (
        Window
        .partitionBy("driver_number")
        .orderBy("lap_number")
        .rowsBetween(Window.unboundedPreceding, 0)
    )
    df = df.withColumn("personal_best", F.min("lap_duration").over(window))
    df = df.withColumn(
        "lap_delta",
        F.col("lap_duration") - F.col("personal_best")
    )
    return df


def add_tyre_degradation_rate(df: DataFrame) -> DataFrame:
    """
    Estimate how much slower (in seconds) the driver gets per lap on this tyre set.
    Partitions by driver + stint_number to handle repeated compounds correctly.
    """
    # Use tyre_age_laps to define a safe divisor
    df = df.withColumn(
        "tyre_age_safe",
        F.when(F.col("tyre_age_laps") > 1, F.col("tyre_age_laps")).otherwise(1)
    )

    # Partition by driver + stint (not compound) so repeated compounds don't merge
    stint_window = (
        Window
        .partitionBy("driver_number", "stint_number")
        .orderBy("lap_number")
    )
    df = df.withColumn(
        "stint_start_lap_time",
        F.first("lap_duration").over(stint_window)
    )
    df = df.withColumn(
        "tyre_degradation_rate_raw",
        (F.col("lap_duration") - F.col("stint_start_lap_time")) / F.col("tyre_age_safe")
    )

    # Clamp to a sane range — anything outside [-0.5, 1.5] is noise/SC/outlier
    df = df.withColumn(
        "tyre_degradation_rate",
        F.when(
            (F.col("tyre_degradation_rate_raw") >= -0.5) &
            (F.col("tyre_degradation_rate_raw") <= 1.5),
            F.col("tyre_degradation_rate_raw")
        ).otherwise(F.lit(None).cast(FloatType()))
    )

    return df.drop("tyre_degradation_rate_raw")


def add_stint_length(df: DataFrame) -> DataFrame:
    """
    Add the current stint length (laps on this tyre set) for each driver.
    Uses tyre_age_laps directly when available, otherwise counts from last pit.
    """
    return df.withColumn(
        "stint_length",
        F.when(
            F.col("tyre_age_laps").isNotNull(),
            F.col("tyre_age_laps")
        ).otherwise(
            F.row_number().over(
                Window.partitionBy("driver_number", "tyre_compound")
                .orderBy("lap_number")
            )
        )
    )


def add_pit_window_prediction(df: DataFrame, deg_threshold: float = 0.15) -> DataFrame:
    """
    Estimate how many more laps the driver can run before needing to pit.
    Logic: if degradation rate is above threshold, the driver should pit soon.
    predicted_laps_remaining = max(0, (threshold - current_deg_rate) / deg_rate_per_lap)
    """
    df = df.withColumn(
        "should_pit_soon",
        F.when(
            F.col("tyre_degradation_rate") > deg_threshold, True
        ).otherwise(False)
    )
    df = df.withColumn(
        "estimated_laps_to_pit",
        F.when(
            F.col("tyre_degradation_rate") > 0,
            F.greatest(
                F.lit(0.0),
                ((F.lit(deg_threshold) - F.col("tyre_degradation_rate")) /
                 F.col("tyre_degradation_rate")).cast(FloatType())
            )
        ).otherwise(F.lit(999.0))
    )
    return df


def compute_all_features(df: DataFrame) -> DataFrame:
    df = df.filter(F.col("lap_duration").isNotNull())
    df = df.filter(F.col("lap_duration") > 60.0)
    df = df.filter(F.col("lap_duration") < 200.0)

    # Derive stint number from tyre_age_laps resets — new stint when age drops
    stint_detect_window = (
        Window
        .partitionBy("driver_number")
        .orderBy("lap_number")
    )
    df = df.withColumn(
        "prev_tyre_age",
        F.lag("tyre_age_laps").over(stint_detect_window)
    )
    df = df.withColumn(
        "is_new_stint",
        F.when(
            (F.col("prev_tyre_age").isNotNull()) &
            (F.col("tyre_age_laps") < F.col("prev_tyre_age")),
            F.lit(1)
        ).otherwise(F.lit(0))
    )
    df = df.withColumn(
        "stint_number",
        F.sum("is_new_stint").over(
            stint_detect_window.rowsBetween(Window.unboundedPreceding, 0)
        )
    )

    df = add_rolling_avg_lap_time(df)
    df = add_lap_delta(df)
    df = add_stint_length(df)
    df = add_tyre_degradation_rate(df)
    df = add_pit_window_prediction(df)

    return df