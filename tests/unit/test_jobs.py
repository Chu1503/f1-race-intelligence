import time

import pandas as pd

from api.jobs import HistoricalJobManager


def test_job_records_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "spark_processing.batch_processor.process_historical_session",
        lambda year, round_number: pd.DataFrame({"lap": [1, 2, 3]}),
    )
    manager = HistoricalJobManager(tmp_path / "jobs.sqlite3")
    job = manager.create(2025, 1)
    for _ in range(50):
        job = manager.get(job["id"])
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.02)
    assert job["status"] == "succeeded"
    assert job["rows_written"] == 3
