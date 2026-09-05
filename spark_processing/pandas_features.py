"""Portable feature engineering used by API/background workers."""
from __future__ import annotations

import numpy as np
import pandas as pd

VALID_LAP_MIN_SECONDS = 60.0
VALID_LAP_MAX_SECONDS = 200.0
DEGRADATION_WINDOW = 5
DEGRADATION_THRESHOLD = 0.15
MAX_DEGRADATION = 1.5


def _rolling_slope(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    if len(clean) >= 3:
        median = float(clean.median())
        clean = clean[(clean - median).abs() <= 3.0]
    if len(clean) < 3:
        return 0.0
    x = np.arange(len(clean), dtype=float)
    slope = float(np.polyfit(x, clean.to_numpy(), 1)[0])
    return float(np.clip(slope, 0.0, MAX_DEGRADATION))


def compute_features_pandas(raw: pd.DataFrame) -> pd.DataFrame:
    """Compute stable per-driver/per-stint lap features without Spark.

    Degradation is a rolling linear trend within the physical tyre stint. It is
    never negative and no longer anchors every sample to the noisy first stint lap.
    """
    required = {"driver_number", "lap_number", "lap_duration"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Missing required lap columns: {', '.join(sorted(missing))}")

    df = raw.copy()
    for column in ("driver_number", "lap_number", "lap_duration", "tyre_age_laps"):
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df[df["lap_duration"].between(VALID_LAP_MIN_SECONDS, VALID_LAP_MAX_SECONDS, inclusive="neither")].copy()
    df = df.dropna(subset=["driver_number", "lap_number"])
    df["driver_number"] = df["driver_number"].astype(int)
    df["lap_number"] = df["lap_number"].astype(int)
    df = df.drop_duplicates(["driver_number", "lap_number"], keep="last")
    df = df.sort_values(["driver_number", "lap_number"]).reset_index(drop=True)

    if "tyre_compound" not in df:
        df["tyre_compound"] = "UNKNOWN"
    df["tyre_compound"] = df["tyre_compound"].fillna("UNKNOWN").astype(str).str.upper()
    if "tyre_age_laps" not in df:
        df["tyre_age_laps"] = np.nan

    by_driver = df.groupby("driver_number", sort=False, group_keys=False)
    age_reset = by_driver["tyre_age_laps"].diff().lt(0)
    compound_change = by_driver["tyre_compound"].shift().ne(df["tyre_compound"])
    first_lap = by_driver.cumcount().eq(0)
    df["stint_number"] = ((age_reset | compound_change | first_lap).groupby(df["driver_number"]).cumsum().astype(int))
    df["stint_length"] = df.groupby(["driver_number", "stint_number"], sort=False).cumcount() + 1
    known_age = df["tyre_age_laps"].notna() & df["tyre_age_laps"].gt(0)
    df.loc[known_age, "stint_length"] = df.loc[known_age, "tyre_age_laps"].astype(int)

    df["rolling_avg_lap_time"] = by_driver["lap_duration"].transform(lambda s: s.rolling(DEGRADATION_WINDOW, min_periods=1).mean())
    df["personal_best"] = by_driver["lap_duration"].cummin()
    df["lap_delta"] = (df["lap_duration"] - df["personal_best"]).clip(lower=0.0)
    df["lap_duration_for_degradation"] = df["lap_duration"]
    if "is_pit_in_lap" in df:
        df.loc[df["is_pit_in_lap"].fillna(False).astype(bool), "lap_duration_for_degradation"] = np.nan
    if "is_pit_out_lap" in df:
        df.loc[df["is_pit_out_lap"].fillna(False).astype(bool), "lap_duration_for_degradation"] = np.nan
    df.loc[df["lap_delta"].gt(10.0), "lap_duration_for_degradation"] = np.nan
    df["tyre_degradation_rate"] = (
        df.groupby(["driver_number", "stint_number"], sort=False)["lap_duration_for_degradation"]
        .transform(lambda s: s.rolling(DEGRADATION_WINDOW, min_periods=3).apply(_rolling_slope, raw=False))
        .fillna(0.0)
        .clip(0.0, MAX_DEGRADATION)
    )
    df["should_pit_soon"] = df["tyre_degradation_rate"].gt(DEGRADATION_THRESHOLD)
    rate = df["tyre_degradation_rate"]
    df["estimated_laps_to_pit"] = np.where(rate.gt(0), np.maximum(0.0, (DEGRADATION_THRESHOLD - rate) / rate), 999.0).astype(float)
    return df.drop(columns=["lap_duration_for_degradation"])
