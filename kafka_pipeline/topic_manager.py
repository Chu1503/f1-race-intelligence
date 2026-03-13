"""
Creates and manages Kafka topics for the F1 pipeline.
Run this once before starting the pipeline to ensure all topics exist.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import KafkaException
from loguru import logger
from config import settings

F1_TOPICS = [
    settings.KAFKA_LAP_DATA_TOPIC,
    settings.KAFKA_PIT_STOPS_TOPIC,
    settings.KAFKA_POSITIONS_TOPIC,
    settings.KAFKA_TELEMETRY_TOPIC,
    "f1.session.events",
    "f1.driver.info",
]

class TopicManager:
    def __init__(self):
        self.admin = AdminClient({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS
        })

    def create_topics(self, num_partitions: int = 1, replication_factor: int = 1):
        new_topics = [
            NewTopic(
                topic,
                num_partitions=num_partitions,
                replication_factor=replication_factor
            )
            for topic in F1_TOPICS
        ]

        futures = self.admin.create_topics(new_topics)

        for topic, future in futures.items():
            try:
                future.result()
                logger.success(f"Created topic: {topic}")
            except KafkaException as e:
                if "TOPIC_ALREADY_EXISTS" in str(e):
                    logger.info(f"Topic already exists (ok): {topic}")
                else:
                    logger.error(f"Failed to create topic {topic}: {e}")
                    raise

    def list_topics(self) -> list[str]:
        """List all topics currently in the broker."""
        metadata = self.admin.list_topics(timeout=10)
        topics = [t for t in metadata.topics.keys() if not t.startswith("__")]
        return sorted(topics)

    def delete_topics(self, topics: list[str] = None):
        """Delete topics. Defaults to all F1 topics."""
        to_delete = topics or F1_TOPICS
        futures = self.admin.delete_topics(to_delete)
        for topic, future in futures.items():
            try:
                future.result()
                logger.warning(f"Deleted topic: {topic}")
            except KafkaException as e:
                logger.error(f"Failed to delete topic {topic}: {e}")