"""
Kafka consumer for the F1 Race Intelligence pipeline.
Reads messages from topics and deserializes them back into dicts.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from typing import Optional, Iterator
from confluent_kafka import Consumer, KafkaException, KafkaError
from loguru import logger
from config import settings


class F1KafkaConsumer:
    def __init__(
        self,
        topics: list[str],
        group_id: str,
        auto_offset_reset: str = "earliest"
    ):

        self.topics = topics
        self.consumer = Consumer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            "session.timeout.ms": 30000,
            "heartbeat.interval.ms": 10000,
        })
        self.consumer.subscribe(topics)
        logger.info(f"Consumer subscribed to {topics} | group={group_id}")

    def consume(
        self,
        timeout: float = 1.0,
        max_messages: Optional[int] = None
    ) -> Iterator[dict]:

        count = 0
        try:
            while True:
                msg = self.consumer.poll(timeout=timeout)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            f"End of partition: {msg.topic()} "
                            f"partition={msg.partition()} offset={msg.offset()}"
                        )
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        raise KafkaException(msg.error())

                try:
                    value = json.loads(msg.value().decode("utf-8"))
                    value["_kafka_topic"] = msg.topic()
                    value["_kafka_offset"] = msg.offset()
                    yield value
                    count += 1
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode message: {e}")
                    continue

                if max_messages and count >= max_messages:
                    logger.info(f"Reached max_messages limit ({max_messages})")
                    break

        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        finally:
            self.close()

    def consume_batch(self, batch_size: int = 100, timeout: float = 5.0) -> list[dict]:
        """
        Consume up to batch_size messages in one call.
        """
        messages = []
        deadline = timeout

        while len(messages) < batch_size:
            msg = self.consumer.poll(timeout=1.0)
            if msg is None:
                deadline -= 1.0
                if deadline <= 0:
                    break
                continue

            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error(f"Consumer error: {msg.error()}")
                continue

            try:
                value = json.loads(msg.value().decode("utf-8"))
                messages.append(value)
            except json.JSONDecodeError:
                continue

        return messages

    def close(self):
        self.consumer.close()
        logger.info("Consumer closed")