import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
import time
from typing import Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from data_ingestion.models import HistoricalRaceResult

BASE_URL = "https://api.jolpi.ca/ergast/f1"


class JolpicaConnector:
    def __init__(self, request_delay: float = 0.3):
        self.client = httpx.Client(
            timeout=20,
            headers={"Accept": "application/json", "User-Agent": "F1-Race-Intelligence/1.0"}
        )
        self.request_delay = request_delay

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{BASE_URL}/{path}.json"
        time.sleep(self.request_delay)
        try:
            response = self.client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Jolpica error {e.response.status_code}: {url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Jolpica request failed: {e}")
            raise

    def get_season_results(
        self, year: int, limit: int = 100
    ) -> list[HistoricalRaceResult]:
        """
        Get all race results for a full season.
        Returns one HistoricalRaceResult per driver per race.
        """
        logger.info(f"Fetching {year} season results from Jolpica...")
        data = self._get(f"{year}/results", params={"limit": limit})

        results = []
        try:
            races = data["MRData"]["RaceTable"]["Races"]
        except (KeyError, TypeError):
            logger.error(f"Unexpected Jolpica response structure for {year}")
            return []

        for race in races:
            race_name = race.get("raceName", "")
            round_num = int(race.get("round", 0))
            circuit_id = race.get("Circuit", {}).get("circuitId", "")

            for result in race.get("Results", []):
                driver = result.get("Driver", {})
                constructor = result.get("Constructor", {})

                finish_pos = result.get("position")
                grid_pos = result.get("grid")

                fastest_lap = result.get("FastestLap", {})
                fastest_lap_time = fastest_lap.get("Time", {}).get("time") if fastest_lap else None

                results.append(HistoricalRaceResult(
                    season=year,
                    round_number=round_num,
                    race_name=race_name,
                    circuit_id=circuit_id,
                    driver_id=driver.get("driverId", ""),
                    constructor_id=constructor.get("constructorId", ""),
                    grid_position=int(grid_pos) if grid_pos and grid_pos != "0" else None,
                    finish_position=int(finish_pos) if finish_pos else None,
                    points=float(result.get("points", 0)),
                    status=result.get("status", "Unknown"),
                    fastest_lap_time=fastest_lap_time,
                    source="jolpica"
                ))

        logger.info(
            f"Fetched {len(results)} driver-race results "
            f"across {len(races)} races in {year}"
        )
        return results

    def get_driver_career_results(
        self, driver_id: str, seasons: list[int] = None
    ) -> list[HistoricalRaceResult]:
        """
        Get all results for one driver across multiple seasons.
        Used to build driver-specific RAG context.
        """
        if seasons is None:
            seasons = list(range(2020, 2025))

        all_results = []
        for year in seasons:
            logger.info(f"Fetching {driver_id} results for {year}...")
            data = self._get(f"{year}/drivers/{driver_id}/results", params={"limit": 50})
            try:
                races = data["MRData"]["RaceTable"]["Races"]
            except (KeyError, TypeError):
                continue

            for race in races:
                for result in race.get("Results", []):
                    driver = result.get("Driver", {})
                    constructor = result.get("Constructor", {})
                    finish_pos = result.get("position")
                    all_results.append(HistoricalRaceResult(
                        season=year,
                        round_number=int(race.get("round", 0)),
                        race_name=race.get("raceName", ""),
                        circuit_id=race.get("Circuit", {}).get("circuitId", ""),
                        driver_id=driver.get("driverId", driver_id),
                        constructor_id=constructor.get("constructorId", ""),
                        grid_position=int(result.get("grid", 0)) or None,
                        finish_position=int(finish_pos) if finish_pos else None,
                        points=float(result.get("points", 0)),
                        status=result.get("status", "Unknown"),
                        fastest_lap_time=None,
                        source="jolpica"
                    ))

        logger.info(
            f"Fetched {len(all_results)} total results for driver '{driver_id}'"
        )
        return all_results

    def get_circuit_history(self, circuit_id: str, seasons: list[int] = None) -> list[HistoricalRaceResult]:
        """
        Get race results at a specific circuit across multiple seasons.
        Used by the RAG agent to answer 'how does X driver perform at Y circuit'.
        """
        if seasons is None:
            seasons = list(range(2018, 2025))

        all_results = []
        for year in seasons:
            data = self._get(f"{year}/circuits/{circuit_id}/results", params={"limit": 100})
            try:
                races = data["MRData"]["RaceTable"]["Races"]
            except (KeyError, TypeError):
                continue

            for race in races:
                for result in race.get("Results", []):
                    driver = result.get("Driver", {})
                    constructor = result.get("Constructor", {})
                    finish_pos = result.get("position")
                    all_results.append(HistoricalRaceResult(
                        season=year,
                        round_number=int(race.get("round", 0)),
                        race_name=race.get("raceName", ""),
                        circuit_id=circuit_id,
                        driver_id=driver.get("driverId", ""),
                        constructor_id=constructor.get("constructorId", ""),
                        grid_position=int(result.get("grid", 0)) or None,
                        finish_position=int(finish_pos) if finish_pos else None,
                        points=float(result.get("points", 0)),
                        status=result.get("status", "Unknown"),
                        fastest_lap_time=None,
                        source="jolpica"
                    ))

        logger.info(f"Fetched {len(all_results)} results at circuit '{circuit_id}'")
        return all_results

    def close(self):
        self.client.close()