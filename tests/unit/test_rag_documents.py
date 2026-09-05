import pandas as pd

from rag_pipeline.ingester import lap_to_document


def test_rag_document_contains_scope_and_observed_outcome():
    row = pd.Series({
        "driver_number": 4, "lap_number": 20, "lap_duration": 91.5,
        "tyre_compound": "MEDIUM", "tyre_age_laps": 12,
        "rolling_avg_lap_time": 91.7, "tyre_degradation_rate": 0.08,
    })
    document = lap_to_document(
        row, 2025, 1, "Albert Park Grand Prix Circuit",
        {"finish_position": 1, "status": "Finished", "points": 25},
        {"lap": 28, "compound": "HARD"},
    )
    assert "Albert Park Grand Prix Circuit" in document
    assert "next pitted on lap 28" in document
    assert "Result P1" in document
