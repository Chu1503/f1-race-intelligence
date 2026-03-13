import sys
from pathlib import Path
from loguru import logger
from config import settings

def setup_logging():
    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.LOG_LEVEL,
        colorize=True,
    )
    # File output: rotates at 50MB, keeps 7 days of logs
    log_path = Path("logs") / "f1_intelligence_{time:YYYY-MM-DD}.log"
    logger.add(
        log_path,
        format=log_format,
        level="DEBUG",
        rotation="50 MB",
        retention="7 days",
        compression="zip",
    )

    logger.info(f"Logging initialized | environment={settings.ENVIRONMENT} | level={settings.LOG_LEVEL}")