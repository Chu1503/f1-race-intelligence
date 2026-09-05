import pandas as pd

from spark_processing.pandas_features import compute_features_pandas


def test_features_split_stints_and_never_report_negative_degradation():
    raw = pd.DataFrame({
        "driver_number": [1] * 8,
        "lap_number": list(range(1, 9)),
        "lap_duration": [92.0, 91.8, 91.6, 91.5, 92.0, 92.2, 92.4, 92.6],
        "tyre_compound": ["MEDIUM"] * 4 + ["HARD"] * 4,
        "tyre_age_laps": [1, 2, 3, 4, 1, 2, 3, 4],
    })
    result = compute_features_pandas(raw)
    assert result["stint_number"].nunique() == 2
    assert (result["tyre_degradation_rate"] >= 0).all()
    assert result.iloc[2]["tyre_degradation_rate"] == 0
    assert result.iloc[-1]["tyre_degradation_rate"] > 0


def test_features_deduplicate_driver_lap_pairs():
    raw = pd.DataFrame({
        "driver_number": [4, 4, 4], "lap_number": [1, 1, 2],
        "lap_duration": [90.0, 89.9, 90.1], "tyre_compound": ["S", "S", "S"],
        "tyre_age_laps": [1, 1, 2],
    })
    result = compute_features_pandas(raw)
    assert list(result["lap_number"]) == [1, 2]
    assert result.iloc[0]["lap_duration"] == 89.9
