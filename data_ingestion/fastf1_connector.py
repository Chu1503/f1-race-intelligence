import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fastf1
import pandas as pd
from pathlib import Path
from typing import Optional
from loguru import logger
from config import settings
from data_ingestion.models import LapData, PitStop, DriverInfo, SessionInfo


class FastF1Connector:
    def __init__(self):
        cache_dir = Path(settings.FASTF1_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(cache_dir))
        logger.info(f"FastF1 cache at: {cache_dir}")

    def load_session(
        self,
        year: int,
        round_number: int,
        session_type: str = "R"
    ) -> fastf1.core.Session:

        logger.info(f"Loading session: {year} Round {round_number} {session_type}")
        session = fastf1.get_session(year, round_number, session_type)
        session.load(
            laps=True,
            telemetry=False,
            weather=True,
            messages=False
        )
        logger.info(
            f"Session loaded: {session.event['EventName']} "
            f"at {session.event['Location']}"
        )
        return session

    def get_session_info(self, session: fastf1.core.Session) -> SessionInfo:
        """Extract normalized session metadata."""
        return SessionInfo(
            session_key=0,
            session_name=session.name,
            session_type=session.name[0],
            year=int(session.event["EventDate"].year),
            circuit_short_name=session.event.get("Location", ""),
            circuit_key=0,
            country_name=session.event.get("Country", ""),
            date_start=str(session.event["EventDate"]),
            gmt_offset="+00:00",
            source="fastf1"
        )

    def get_laps(self, session: fastf1.core.Session) -> list[LapData]:
        laps_df = session.laps.copy()

        # Convert timedelta columns to seconds floats
        def td_to_seconds(val) -> Optional[float]:
            if pd.isna(val) or val is None:
                return None
            try:
                return val.total_seconds()
            except AttributeError:
                return float(val)

        lap_list = []
        for _, row in laps_df.iterrows():
            lap_time = td_to_seconds(row.get("LapTime"))
            # Skip laps with no time (incomplete laps)
            if lap_time is None:
                continue

            lap_list.append(LapData(
                session_key=0,
                driver_number=int(row.get("DriverNumber", 0)),
                lap_number=int(row.get("LapNumber", 0)),
                lap_duration=lap_time,
                sector_1_time=td_to_seconds(row.get("Sector1Time")),
                sector_2_time=td_to_seconds(row.get("Sector2Time")),
                sector_3_time=td_to_seconds(row.get("Sector3Time")),
                tyre_compound=row.get("Compound"),
                tyre_age_laps=int(row.get("TyreLife", 0)) if pd.notna(row.get("TyreLife")) else None,
                is_pit_out_lap=bool(row.get("PitOutTime") is not None and pd.notna(row.get("PitOutTime"))),
                is_pit_in_lap=bool(row.get("PitInTime") is not None and pd.notna(row.get("PitInTime"))),
                source="fastf1"
            ))

        logger.info(f"Extracted {len(lap_list)} valid laps from FastF1 session")
        return lap_list

    def get_drivers(self, session: fastf1.core.Session) -> list[DriverInfo]:
        """Get driver info from a FastF1 session."""
        drivers = []
        for driver_number in session.drivers:
            try:
                driver = session.get_driver(driver_number)
                num = int(driver.get("DriverNumber", 0))
                drivers.append(DriverInfo(
                    driver_number=num,
                    full_name=driver.get("FullName", ""),
                    abbreviation=driver.get("Abbreviation", ""),
                    team_name=driver.get("TeamName", ""),
                    team_colour=f"#{driver.get('TeamColor', '000000')}",
                    source="fastf1"
                ))
            except Exception as e:
                logger.warning(f"Could not get info for driver {driver_number}: {e}")
                continue
        return drivers

    def get_pit_stops(self, session: fastf1.core.Session) -> list[PitStop]:
        """Extract pit stop events from lap data."""
        laps_df = session.laps.copy()
        pit_laps = laps_df[
            laps_df["PitInTime"].notna() | laps_df["PitOutTime"].notna()
        ]

        pits = []
        for _, row in pit_laps.iterrows():
            if pd.notna(row.get("PitInTime")):
                pits.append(PitStop(
                    session_key=0,
                    driver_number=int(row.get("DriverNumber", 0)),
                    lap_number=int(row.get("LapNumber", 0)),
                    pit_duration=None,  # computed from PitInTime-PitOutTime in Spark
                    tyre_compound_new=row.get("Compound"),
                    source="fastf1"
                ))
        logger.info(f"Extracted {len(pits)} pit stops")
        return pits

    def get_race_replay_generator(
        self,
        session: fastf1.core.Session,
        delay_seconds: float = 1.0
    ):
        """
        Generator that yields laps one at a time, simulating a live race.
        Used in development when there's no live race weekend.
        """
        import time
        all_laps = self.get_laps(session)
        # Group by lap number to simulate laps completing together
        from collections import defaultdict
        laps_by_number: dict = defaultdict(list)
        for lap in all_laps:
            laps_by_number[lap.lap_number].append(lap)

        logger.info(
            f"Starting race replay: {len(laps_by_number)} laps, "
            f"{delay_seconds}s delay between laps"
        )

        for lap_number in sorted(laps_by_number.keys()):
            lap_group = laps_by_number[lap_number]
            logger.info(
                f"[REPLAY] Lap {lap_number}: "
                f"{len(lap_group)} drivers completing lap"
            )
            for lap in lap_group:
                yield lap
            time.sleep(delay_seconds)