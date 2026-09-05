from data_ingestion.openf1_connector import OpenF1Connector


def test_laps_join_compound_and_tyre_age_from_stints(monkeypatch):
    connector = OpenF1Connector()
    responses = {
        "laps": [{"driver_number": 1, "lap_number": 8, "lap_duration": 91.2}],
        "stints": [{"driver_number": 1, "lap_start": 6, "lap_end": 12, "compound": "HARD", "tyre_age_at_start": 2}],
    }
    monkeypatch.setattr(connector, "_get", lambda endpoint, params=None: responses[endpoint])
    lap = connector.get_laps(99)[0]
    assert lap.tyre_compound == "HARD"
    assert lap.tyre_age_laps == 4
    connector.close()


def test_per_driver_watermarks_do_not_drop_a_slow_driver(monkeypatch):
    connector = OpenF1Connector()
    laps = [
        type("Lap", (), {"driver_number": 1, "lap_number": 10})(),
        type("Lap", (), {"driver_number": 2, "lap_number": 8})(),
    ]
    monkeypatch.setattr(connector, "get_laps", lambda session_key: laps)
    result = connector.get_latest_laps_since(99, {1: 10, 2: 7})
    assert [(lap.driver_number, lap.lap_number) for lap in result] == [(2, 8)]
    connector.close()
