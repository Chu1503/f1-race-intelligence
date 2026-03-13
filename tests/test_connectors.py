import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from logger_config import setup_logging
setup_logging()


def test_openf1():
    logger.info("\nTesting OpenF1 Connector")
    from data_ingestion.openf1_connector import OpenF1Connector
    conn = OpenF1Connector()

    session = conn.get_latest_session_with_data()
    if not session:
        logger.error("FAIL: Could not fetch latest session")
        return False

    logger.success(f"PASS: Latest session = {session.session_name} | {session.country_name} {session.year}")

    drivers = conn.get_drivers(session.session_key)
    logger.success(f"PASS: Got {len(drivers)} drivers")
    for d in drivers[:3]:
        logger.info(f"  {d.abbreviation} ({d.driver_number}) | {d.team_name}")

    laps = conn.get_laps(session.session_key)
    logger.success(f"PASS: Got {len(laps)} laps")
    if laps:
        sample = laps[0]
        logger.info(
            f"  Sample: Driver {sample.driver_number}, "
            f"Lap {sample.lap_number}, Time {sample.lap_duration:.3f}s, "
            f"Tyre: {sample.tyre_compound}"
        )

    pits = conn.get_pit_stops(session.session_key)
    logger.success(f"PASS: Got {len(pits)} pit stops")

    positions = conn.get_positions(session.session_key)
    logger.success(f"PASS: Got {len(positions)} driver positions")
    if positions:
        leader = positions[0]
        logger.info(f"  Leader: Driver {leader.driver_number} in P{leader.position}")

    conn.close()
    return True


def test_fastf1():
    logger.info("\nTesting FastF1 Connector")
    from data_ingestion.fastf1_connector import FastF1Connector
    from config import settings

    conn = FastF1Connector()
    logger.info(f"Loading {settings.REPLAY_YEAR} Round {settings.REPLAY_ROUND} Race...")

    try:
        session = conn.load_session(
            year=settings.REPLAY_YEAR,
            round_number=settings.REPLAY_ROUND,
            session_type=settings.REPLAY_SESSION
        )
    except Exception as e:
        logger.error(f"FAIL: Could not load FastF1 session: {e}")
        return False

    info = conn.get_session_info(session)
    logger.success(f"PASS: Loaded session = {info.session_name} at {info.circuit_short_name}")

    laps = conn.get_laps(session)
    logger.success(f"PASS: Got {len(laps)} laps from FastF1")

    drivers = conn.get_drivers(session)
    logger.success(f"PASS: Got {len(drivers)} drivers from FastF1")

    pits = conn.get_pit_stops(session)
    logger.success(f"PASS: Got {len(pits)} pit stops from FastF1")

    logger.info("Testing replay generator (first 3 laps)...")
    count = 0
    for lap in conn.get_race_replay_generator(session, delay_seconds=0):
        logger.info(f"  [REPLAY] Driver {lap.driver_number} | Lap {lap.lap_number} | {lap.lap_duration:.3f}s")
        count += 1
        if count >= 5:
            break
    logger.success(f"PASS: Replay generator works")
    return True


def test_jolpica():
    logger.info("\nTesting Jolpica Connector")
    from data_ingestion.jolpica_connector import JolpicaConnector

    conn = JolpicaConnector()

    results = conn.get_season_results(2024, limit=30)
    if not results:
        logger.error("FAIL: No results from Jolpica")
        return False

    logger.success(f"PASS: Got {len(results)} driver-race results for 2024")
    sample = results[0]
    logger.info(
        f"  Sample: {sample.driver_id} at {sample.race_name} "
        f"— P{sample.finish_position} ({sample.status})"
    )

    logger.info("Fetching Verstappen's 2024 results...")
    ver_results = conn.get_driver_career_results("max_verstappen", seasons=[2024])
    logger.success(f"PASS: Got {len(ver_results)} results for Verstappen in 2024")

    conn.close()
    return True


def main():
    logger.info("Data Ingestion Tests")

    results = {
        "OpenF1 API": test_openf1(),
        "FastF1 Library": test_fastf1(),
        "Jolpica API": test_jolpica(),
    }

    logger.info("\n" + "=" * 60)
    passed = sum(results.values())
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        logger.info(f"[{status}] {name}")
    logger.info(f"\n{passed}/3 connectors working")
    if passed == 3:
        logger.success("Success!")
    return passed == 3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)