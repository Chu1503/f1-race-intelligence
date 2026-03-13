import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
from typing import Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from data_ingestion.models import (
    LapData, DriverPosition, PitStop, DriverInfo, SessionInfo
)

BASE_URL = "https://api.openf1.org/v1"


class OpenF1Connector:
    def __init__(self, timeout: int = 15):
        self.client = httpx.Client(timeout=timeout, headers={
            "Accept": "application/json",
            "User-Agent": "F1-Race-Intelligence/1.0"
        })

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _get(self, endpoint: str, params: dict = None) -> list[dict]:
        url = f"{BASE_URL}/{endpoint}"
        try:
            response = self.client.get(url, params=params or {})
            if response.status_code == 404:
                logger.warning(f"OpenF1 {endpoint} returned 404 data not yet available for this session")
                return []
            response.raise_for_status()
            data = response.json()
            logger.debug(f"OpenF1 {endpoint}: {len(data)} records")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenF1 HTTP error {e.response.status_code} for {url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"OpenF1 request failed for {url}: {e}")
            raise

    def get_latest_session(self) -> Optional[SessionInfo]:
        """Get the most recent F1 session (live or just completed)"""
        data = self._get("sessions", params={"session_type": "Race"})
        if not data:
            logger.warning("No sessions found from OpenF1")
            return None

        latest = data[-1]
        return SessionInfo(
            session_key=latest["session_key"],
            session_name=latest.get("session_name", "Race"),
            session_type=latest.get("session_type", "R"),
            year=latest.get("year", 0),
            circuit_short_name=latest.get("circuit_short_name", ""),
            circuit_key=latest.get("circuit_key", 0),
            country_name=latest.get("country_name", ""),
            date_start=latest.get("date_start", ""),
            gmt_offset=latest.get("gmt_offset", "+00:00"),
            source="openf1"
        )

    def get_session_by_key(self, session_key: int) -> Optional[SessionInfo]:
        """Get a specific session by its key."""
        data = self._get("sessions", params={"session_key": session_key})
        if not data:
            return None
        s = data[0]
        return SessionInfo(
            session_key=s["session_key"],
            session_name=s.get("session_name", ""),
            session_type=s.get("session_type", ""),
            year=s.get("year", 0),
            circuit_short_name=s.get("circuit_short_name", ""),
            circuit_key=s.get("circuit_key", 0),
            country_name=s.get("country_name", ""),
            date_start=s.get("date_start", ""),
            gmt_offset=s.get("gmt_offset", "+00:00"),
            source="openf1"
        )
    
    def get_latest_session_with_data(self) -> Optional[SessionInfo]:
        import time
        from datetime import datetime

        current_year = datetime.utcnow().year

        # Try current year first, then fall back to previous year
        for year in [current_year, current_year - 1]:
            data = self._get("sessions", params={"session_type": "Race", "year": year})
            if not data:
                logger.warning(f"No race sessions found for {year}")
                continue

            # Only probe the 5 most recent
            candidates = list(reversed(data))[:5]
            logger.info(f"Probing {len(candidates)} most recent sessions from {year}...")

            for s in candidates:
                key = s["session_key"]
                time.sleep(1.0)
                test = self._get("laps", params={"session_key": key, "lap_number": 1})
                if test:
                    logger.info(
                        f"Found session with lap data: "
                        f"key={key} | {s['country_name']} {s['year']}"
                    )
                    return SessionInfo(
                        session_key=key,
                        session_name=s.get("session_name", "Race"),
                        session_type=s.get("session_type", "R"),
                        year=s.get("year", 0),
                        circuit_short_name=s.get("circuit_short_name", ""),
                        circuit_key=s.get("circuit_key", 0),
                        country_name=s.get("country_name", ""),
                        date_start=s.get("date_start", ""),
                        gmt_offset=s.get("gmt_offset", "+00:00"),
                        source="openf1"
                    )
                logger.warning(
                    f"Session key={key} ({s['country_name']} {s['year']}) "
                    f": no lap data yet, skipping"
                )

        logger.error(
            "Could not find any session with lap data in "
            f"{current_year} or {current_year - 1}"
        )
        return None

    def get_drivers(self, session_key: int) -> list[DriverInfo]:
        """Get all drivers in a session."""
        data = self._get("drivers", params={"session_key": session_key})
        drivers = []
        for d in data:
            drivers.append(DriverInfo(
                driver_number=d["driver_number"],
                full_name=d.get("full_name", ""),
                abbreviation=d.get("name_acronym", ""),
                team_name=d.get("team_name", ""),
                team_colour=f"#{d.get('team_colour', '000000')}",
                headshot_url=d.get("headshot_url"),
                country_code=d.get("country_code"),
                source="openf1"
            ))
        logger.info(f"Loaded {len(drivers)} drivers for session {session_key}")
        return drivers

    def get_laps(
        self,
        session_key: int,
        driver_number: Optional[int] = None,
        lap_number: Optional[int] = None
    ) -> list[LapData]:
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        if lap_number:
            params["lap_number"] = lap_number

        data = self._get("laps", params=params)
        laps = []
        for lap in data:
            laps.append(LapData(
                session_key=session_key,
                driver_number=lap["driver_number"],
                lap_number=lap["lap_number"],
                lap_duration=lap.get("lap_duration"),
                sector_1_time=lap.get("duration_sector_1"),
                sector_2_time=lap.get("duration_sector_2"),
                sector_3_time=lap.get("duration_sector_3"),
                tyre_compound=lap.get("compound"),
                tyre_age_laps=lap.get("tyre_age_at_start"),
                is_pit_out_lap=lap.get("is_pit_out_lap", False),
                is_pit_in_lap=False,
                source="openf1"
            ))
        return laps

    def get_positions(self, session_key: int) -> list[DriverPosition]:
        """Get current race positions for all drivers."""
        data = self._get("position", params={"session_key": session_key})

        latest_per_driver: dict[int, dict] = {}
        for entry in data:
            num = entry["driver_number"]
            if num not in latest_per_driver:
                latest_per_driver[num] = entry
            else:
                if entry.get("date", "") > latest_per_driver[num].get("date", ""):
                    latest_per_driver[num] = entry

        positions = []
        for num, entry in latest_per_driver.items():
            positions.append(DriverPosition(
                session_key=session_key,
                driver_number=num,
                position=entry.get("position", 99),
                gap_to_leader=None,
                interval=None,
                timestamp=entry.get("date", ""),
                source="openf1"
            ))

        return sorted(positions, key=lambda p: p.position)

    def get_pit_stops(self, session_key: int) -> list[PitStop]:
        """Get all pit stops in a session."""
        data = self._get("pit", params={"session_key": session_key})
        pits = []
        for p in data:
            pits.append(PitStop(
                session_key=session_key,
                driver_number=p["driver_number"],
                lap_number=p.get("lap_number", 0),
                pit_duration=p.get("pit_duration"),
                tyre_compound_new=None,  # joined with stint data in Spark
                timestamp=p.get("date", ""),
                source="openf1"
            ))
        return pits

    def get_latest_laps_since(
        self, session_key: int, after_lap: int
    ) -> list[LapData]:
        """
        Poll for new laps since the last one we processed.
        This is what the Ingestion Agent calls in a loop during live races.
        """
        all_laps = self.get_laps(session_key=session_key)
        new_laps = [lap for lap in all_laps if lap.lap_number > after_lap]
        if new_laps:
            logger.info(
                f"Found {len(new_laps)} new laps "
                f"(laps {min(l.lap_number for l in new_laps)}-"
                f"{max(l.lap_number for l in new_laps)})"
            )
        return new_laps

    def close(self):
        self.client.close()