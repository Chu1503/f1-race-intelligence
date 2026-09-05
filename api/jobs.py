from __future__ import annotations

import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoricalJobManager:
    """Single-worker, SQLite-backed historical ingestion queue."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or settings.JOB_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="historical-worker")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id TEXT PRIMARY KEY,
                    year INTEGER NOT NULL,
                    round_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    error TEXT,
                    rows_written INTEGER,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
            """)
            connection.execute(
                "UPDATE processing_jobs SET status='failed', error=?, finished_at=? WHERE status IN ('queued','running')",
                ("Worker process restarted before the job completed.", _now()),
            )

    def create(self, year: int, round_number: int) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            active = connection.execute(
                "SELECT * FROM processing_jobs WHERE year=? AND round_number=? AND status IN ('queued','running') ORDER BY created_at DESC LIMIT 1",
                (year, round_number),
            ).fetchone()
            if active:
                return dict(active)
            job_id = uuid.uuid4().hex
            created = _now()
            connection.execute(
                "INSERT INTO processing_jobs (id, year, round_number, status, message, created_at) VALUES (?, ?, ?, 'queued', ?, ?)",
                (job_id, year, round_number, "Waiting for the ingestion worker.", created),
            )
        self._executor.submit(self._run, job_id, year, round_number)
        return self.get(job_id)

    def _update(self, job_id: str, **values: Any) -> None:
        if not values:
            return
        columns = ", ".join(f"{name}=?" for name in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE processing_jobs SET {columns} WHERE id=?",
                (*values.values(), job_id),
            )

    def _run(self, job_id: str, year: int, round_number: int) -> None:
        self._update(job_id, status="running", message="Downloading and processing race laps.", started_at=_now())
        try:
            from spark_processing.batch_processor import process_historical_session
            frame = process_historical_session(year, round_number)
            self._update(
                job_id,
                status="succeeded",
                message="Race data is ready.",
                rows_written=len(frame),
                finished_at=_now(),
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                message="Race processing failed.",
                error=str(exc)[:2000],
                finished_at=_now(),
            )

    def get(self, job_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM processing_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return dict(row)


job_manager = HistoricalJobManager()
