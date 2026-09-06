import json
from pathlib import Path

from scripts import process_all_seasons


def test_completed_rounds_come_from_calendar_dates(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "MRData": {
                    "RaceTable": {
                        "Races": [
                            {"round": "1", "raceName": "Past Grand Prix", "date": "2000-01-01"},
                            {"round": "2", "raceName": "Future Grand Prix", "date": "2999-01-01"},
                        ]
                    }
                }
            }

    monkeypatch.setattr(process_all_seasons.requests, "get", lambda *_args, **_kwargs: Response())

    assert process_all_seasons.get_completed_rounds(2024) == [(1, "Past GP")]


def test_static_archive_manifest_and_bundles_are_consistent():
    project_root = Path(__file__).resolve().parents[2]
    manifest_path = project_root / "frontend" / "public" / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    available_keys = {f"{race['year']}-{race['round']}" for race in manifest["availableRaces"]}
    assert set(manifest["raceFiles"]) == available_keys
    assert {2023, 2024, 2025, 2026}.issubset({race["year"] for race in manifest["availableRaces"]})

    public_root = (project_root / "frontend" / "public").resolve()
    for race_key, url in manifest["raceFiles"].items():
        bundle_path = (public_root / url.lstrip("/")).resolve()
        assert public_root in bundle_path.parents
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert bundle["laps"], race_key
        assert bundle["driverStats"], race_key
        assert bundle["results"], race_key
        assert bundle["lapPositions"], race_key
        assert bundle["fastestLaps"], race_key
        assert bundle["tyreStrategies"], race_key
        assert bundle["pitStops"], race_key
