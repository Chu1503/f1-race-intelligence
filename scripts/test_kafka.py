import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from loguru import logger
from logger_config import setup_logging
from config import settings

setup_logging()


def test_kafka_connection():
    logger.info("\nTesting Kafka Connection")
    from kafka_pipeline.topic_manager import TopicManager
    try:
        manager = TopicManager()
        manager.create_topics()
        topics = manager.list_topics()
        logger.success(f"PASS: Kafka connected. Topics: {topics}")
        return True
    except Exception as e:
        logger.error(f"FAIL: Cannot connect to Kafka: {e}")
        logger.error("Make sure Docker is running and you started Kafka with:")
        logger.error("  docker-compose -f docker/docker-compose.kafka.yml up -d")
        return False


def test_produce_consume():
    logger.info("\nesting Producer Consumer Round Trip")
    from kafka_pipeline.producer import F1KafkaProducer
    from kafka_pipeline.consumer import F1KafkaConsumer
    from data_ingestion.models import LapData

    # Create a test lap
    test_lap = LapData(
        session_key=9999,
        driver_number=1,
        lap_number=42,
        lap_duration=91.234,
        sector_1_time=28.1,
        sector_2_time=32.4,
        sector_3_time=30.7,
        tyre_compound="SOFT",
        tyre_age_laps=5,
        source="test"
    )

    producer = F1KafkaProducer()
    producer.publish_lap(test_lap)
    flushed = producer.flush()
    logger.success(f"PASS: Published test lap, flush remaining={flushed}")

    consumer = F1KafkaConsumer(
        topics=[settings.KAFKA_LAP_DATA_TOPIC],
        group_id="test-consumer",
        auto_offset_reset="earliest"
    )

    logger.info("Waiting for message (up to 10 seconds)...")
    received = []
    for msg in consumer.consume(timeout=1.0, max_messages=1):
        received.append(msg)
        logger.success(
            f"PASS: Received message — "
            f"driver={msg.get('driver_number')} "
            f"lap={msg.get('lap_number')} "
            f"time={msg.get('lap_duration')}s "
            f"tyre={msg.get('tyre_compound')}"
        )
        break

    if not received:
        logger.error("FAIL: No message received within timeout")
        return False

    # Verify round-trip data integrity
    msg = received[0]
    assert msg["driver_number"] == 1, "driver_number mismatch"
    assert msg["lap_number"] == 42, "lap_number mismatch"
    assert msg["lap_duration"] == 91.234, "lap_duration mismatch"
    assert msg["tyre_compound"] == "SOFT", "tyre_compound mismatch"
    logger.success("PASS: All fields survived the Kafka round trip correctly")
    return True


def test_replay_to_kafka():
    logger.info("\nTesting Replay Pipeline (5 laps into Kafka)")
    from kafka_pipeline.ingestion_agent import IngestionAgent
    from kafka_pipeline.consumer import F1KafkaConsumer

    agent = IngestionAgent()

    # Load session and push 5 laps
    from data_ingestion.fastf1_connector import FastF1Connector
    from config import settings

    ff1 = FastF1Connector()
    session = ff1.load_session(settings.REPLAY_YEAR, settings.REPLAY_ROUND, "R")

    count = 0
    for lap in ff1.get_race_replay_generator(session, delay_seconds=0):
        agent.producer.publish_lap(lap)
        count += 1
        if count >= 20:
            break

    agent.producer.flush()
    logger.success(f"PASS: Published {count} replay laps to Kafka")

    consumer = F1KafkaConsumer(
        topics=[settings.KAFKA_LAP_DATA_TOPIC],
        group_id="test-replay-consumer",
        auto_offset_reset="earliest"
    )

    received = list(consumer.consume(timeout=2.0, max_messages=20))
    logger.success(f"PASS: Consumed {len(received)} messages back from Kafka")

    if received:
        sample = received[0]
        logger.info(
            f"  Sample: driver={sample.get('driver_number')} "
            f"lap={sample.get('lap_number')} "
            f"time={sample.get('lap_duration')}s"
        )

    return len(received) > 0


def main():
    logger.info("Kafka Pipeline Tests")

    results = {
        "Kafka Connection": test_kafka_connection(),
        "Producer Consumer Round Trip": test_produce_consume(),
        "Replay to Kafka": test_replay_to_kafka(),
    }

    passed = sum(results.values())
    for name, ok in results.items():
        logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}")
    logger.info(f"\n{passed}/3 tests passed")

    if passed == 3:
        logger.success("Kafka pipeline is live")
    return passed == 3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)