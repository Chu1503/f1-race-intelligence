import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from typing import Optional, Callable
from confluent_kafka import Producer, KafkaException
from loguru import logger
from config import settings


class F1KafkaProducer:
    def __init__(self):
        self.producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "f1-ingestion-agent",
            "retries": 5,
            "retry.backoff.ms": 500,
            "linger.ms": 10,
            "batch.size": 16384,
            "compression.type": "snappy",
        })
        self._published_count = 0
        logger.info(f"Kafka producer connected to {settings.KAFKA_BOOTSTRAP_SERVERS}")

    def _delivery_callback(self, err, msg):
        if err:
            logger.error(f"Message delivery failed: topic={msg.topic()} error={err}")
        else:
            self._published_count += 1
            logger.debug(
                f"Delivered to {msg.topic()} "
                f"partition={msg.partition()} offset={msg.offset()}"
            )

    def _publish(self, topic: str, key: str, value: dict):
        try:
            self.producer.produce(
                topic=topic,
                key=key.encode("utf-8"),
                value=json.dumps(value).encode("utf-8"),
                callback=self._delivery_callback,
            )
            self.producer.poll(0)
        except KafkaException as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise
        except BufferError:
            logger.warning("Kafka producer queue full: flushing before retry")
            self.producer.flush(timeout=5)
            self._publish(topic, key, value)

    def publish_lap(self, lap) -> None:
        key = f"{lap.session_key}:{lap.driver_number}:{lap.lap_number}"
        self._publish(settings.KAFKA_LAP_DATA_TOPIC, key, lap.to_dict())

    def publish_pit_stop(self, pit) -> None:
        key = f"{pit.session_key}:{pit.driver_number}:{pit.lap_number}"
        self._publish(settings.KAFKA_PIT_STOPS_TOPIC, key, pit.to_dict())

    def publish_position(self, position) -> None:
        key = f"{position.session_key}:{position.driver_number}"
        self._publish(settings.KAFKA_POSITIONS_TOPIC, key, position.to_dict())

    def publish_session_event(self, event_type: str, data: dict) -> None:
        payload = {"event_type": event_type, **data}
        self._publish("f1.session.events", event_type, payload)

    def flush(self, timeout: int = 10) -> int:
        """
        Wait for all queued messages to be delivered.
        Call this at the end of a batch or before shutting down.
        Returns number of messages still in queue (should be 0).
        """
        remaining = self.producer.flush(timeout=timeout)
        if remaining > 0:
            logger.warning(f"{remaining} messages not delivered after flush")
        else:
            logger.debug(f"All messages delivered. Total published: {self._published_count}")
        return remaining

    def close(self):
        self.flush()
        logger.info(f"Producer closed. Total messages published: {self._published_count}")