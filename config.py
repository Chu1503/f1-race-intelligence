import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

class Settings:
    PROJECT_ROOT: Path = Path(__file__).parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    FASTF1_CACHE_DIR: Path = Path(os.getenv("FASTF1_CACHE_DIR", "./data/fastf1_cache"))

    # API Keys
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
    VOYAGE_API_KEY: str = os.getenv("VOYAGE_API_KEY", "")

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_LAP_DATA_TOPIC: str = os.getenv("KAFKA_LAP_DATA_TOPIC", "f1.lap.data")
    KAFKA_TELEMETRY_TOPIC: str = os.getenv("KAFKA_TELEMETRY_TOPIC", "f1.telemetry")
    KAFKA_PIT_STOPS_TOPIC: str = os.getenv("KAFKA_PIT_STOPS_TOPIC", "f1.pit.stops")
    KAFKA_POSITIONS_TOPIC: str = os.getenv("KAFKA_POSITIONS_TOPIC", "f1.positions")

    # Spark
    SPARK_MASTER_URL: str = os.getenv("SPARK_MASTER_URL", "local[*]")
    SPARK_APP_NAME: str = os.getenv("SPARK_APP_NAME", "F1RaceIntelligence")

    # BigQuery
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "f1_race_data")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))
    STREAMLIT_PORT: int = int(os.getenv("STREAMLIT_PORT", "8501"))

    # LLM Model Settings
    # CLAUDE_MODEL = "claude-sonnet-4-6"
    CLAUDE_MODEL = "claude-haiku-4-5-20251001"
    CLAUDE_MAX_TOKENS: int = 4096

    # Used when replaying historical races in dev mode (no live race weekend)
    REPLAY_YEAR: int = 2024
    REPLAY_ROUND: int = 1       # Race number within the season
    REPLAY_SESSION: str = "R"   # R=Race, Q=Qualifying, FP1/FP2/FP3

    def validate(self) -> bool:
        """Check that critical settings are present. Call at startup."""
        errors = []
        if not self.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is not set")
        if not self.PINECONE_API_KEY:
            errors.append("PINECONE_API_KEY is not set")
        if not self.VOYAGE_API_KEY:
            errors.append("VOYAGE_API_KEY is not set")
        if errors:
            for error in errors:
                logger.warning(f"Config warning: {error}")
            return False
        logger.info("Configuration validated successfully")
        return True

    def create_data_dirs(self):
        """Create required local directories if they don't exist."""
        dirs = [
            self.DATA_DIR,
            self.FASTF1_CACHE_DIR,
            self.PROJECT_ROOT / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        logger.info(f"Data directories ready: {self.DATA_DIR}")

settings = Settings()