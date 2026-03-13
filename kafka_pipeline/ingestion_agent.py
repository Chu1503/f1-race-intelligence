import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import signal
from loguru import logger
from logger_config import setup_logging

from config import settings
from data_ingestion.openf1_connector import OpenF1Connector
from data_ingestion.fastf1_connector import FastF1Connector
from kafka_pipeline.producer import F1KafkaProducer
from kafka_pipeline.topic_manager import TopicManager

setup_logging()

_running = True
def _handle_shutdown(sig, frame):
    global _running
    logger.info("Shutdown signal received: finishing current lap then stopping")
    _running = False

signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


class IngestionAgent:
    """
    Polls F1 data sources and streams events into Kafka.
    Automatically uses replay mode when no live session is available.
    """

    def __init__(self):
        self.producer = F1KafkaProducer()
        self.openf1 = OpenF1Connector()
        self.fastf1 = FastF1Connector()
        self._last_lap_number = 0
        self._published_laps = 0
        self._published_pits = 0

    def _setup_topics(self):
        manager = TopicManager()
        manager.create_topics()
        existing = manager.list_topics()
        logger.info(f"Active topics: {existing}")

    def run_live(self, session_key: int, poll_interval: float = 2.0):
        """
        Live race mode: poll OpenF1 every poll_interval seconds.
        Publishes new laps, pit stops, and positions to Kafka as they arrive.
        """
        logger.info(f"Starting LIVE ingestion for session {session_key}")
        self._setup_topics()

        # Publish session start event
        session = self.openf1.get_session_by_key(session_key)
        if session:
            self.producer.publish_session_event("session_start", session.to_dict())

        # Publish driver roster
        drivers = self.openf1.get_drivers(session_key)
        for driver in drivers:
            self.producer._publish("f1.driver.info", str(driver.driver_number), driver.to_dict())

        logger.info(f"Published {len(drivers)} drivers. Starting lap polling...")

        while _running:
            try:
                # Fetch only new laps since last poll
                new_laps = self.openf1.get_latest_laps_since(
                    session_key, self._last_lap_number
                )
                for lap in new_laps:
                    self.producer.publish_lap(lap)
                    self._published_laps += 1
                    if lap.lap_number > self._last_lap_number:
                        self._last_lap_number = lap.lap_number

                # Fetch current positions
                positions = self.openf1.get_positions(session_key)
                for pos in positions:
                    self.producer.publish_position(pos)

                # Fetch pit stops
                pits = self.openf1.get_pit_stops(session_key)
                for pit in pits:
                    self.producer.publish_pit_stop(pit)
                    self._published_pits += 1

                if new_laps:
                    logger.info(
                        f"Lap {self._last_lap_number} | "
                        f"+{len(new_laps)} laps | "
                        f"{len(pits)} total pit stops | "
                        f"{len(positions)} positions published"
                    )

                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Polling error: {e} retrying in 5s")
                time.sleep(5)

        self.producer.flush()
        logger.info(
            f"Live ingestion stopped. "
            f"Published: {self._published_laps} laps, "
            f"{self._published_pits} pit stops"
        )

    def run_replay(self, year: int, round_number: int, lap_delay: float = 0.5):
        """
        Replay mode: streams a historical race through Kafka at accelerated speed.
        """
        logger.info(
            f"Starting REPLAY ingestion: {year} Round {round_number} "
            f"(1 lap every {lap_delay}s)"
        )
        self._setup_topics()

        session = self.fastf1.load_session(year, round_number, "R")

        drivers = self.fastf1.get_drivers(session)
        for driver in drivers:
            self.producer._publish("f1.driver.info", str(driver.driver_number), driver.to_dict())

        info = self.fastf1.get_session_info(session)
        self.producer.publish_session_event("session_start", info.to_dict())

        logger.info(f"Replaying {info.circuit_short_name} {year}...")

        for lap in self.fastf1.get_race_replay_generator(session, delay_seconds=lap_delay):
            if not _running:
                break
            self.producer.publish_lap(lap)
            self._published_laps += 1
            logger.info(
                f"[REPLAY] Lap {lap.lap_number} | "
                f"Driver {lap.driver_number} | "
                f"{lap.lap_duration:.3f}s | "
                f"Tyre: {lap.tyre_compound}"
            )

        # Publish all pit stops at the end
        pits = self.fastf1.get_pit_stops(session)
        for pit in pits:
            self.producer.publish_pit_stop(pit)
            self._published_pits += 1

        self.producer.publish_session_event("session_end", {"source": "fastf1"})
        self.producer.flush()

        logger.success(
            f"Replay complete: {self._published_laps} laps, "
            f"{self._published_pits} pit stops published to Kafka"
        )


if __name__ == "__main__":
    agent = IngestionAgent()

    # In development, always use replay mode
    agent.run_replay(
        year=settings.REPLAY_YEAR,
        round_number=settings.REPLAY_ROUND,
        lap_delay=0.3
    )