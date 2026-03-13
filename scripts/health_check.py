import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loguru import logger
from logger_config import setup_logging
from config import settings

setup_logging()

def check_python_version():
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 11
    status = "PASS" if ok else "FAIL"
    logger.info(f"[{status}] Python version: {version.major}.{version.minor}.{version.micro}")
    return ok

def check_imports():
    packages = {
        "fastf1": "FastF1 historical data library",
        "confluent_kafka": "Kafka Python client",
        "pyspark": "Apache Spark",
        "anthropic": "Anthropic Claude SDK",
        "crewai": "CrewAI multi-agent framework",
        "langgraph": "LangGraph for feedback loops",
        "pinecone": "Pinecone vector database",
        "fastapi": "FastAPI web framework",
        "streamlit": "Streamlit dashboard",
        "pandas": "Pandas data processing",
        "loguru": "Loguru logging",
        "dotenv": "python-dotenv env loading",
    }
    all_ok = True
    for module, description in packages.items():
        try:
            __import__(module)
            logger.info(f"[PASS] {description} ({module})")
        except ImportError as e:
            logger.error(f"[FAIL] {description} ({module}): {e}")
            all_ok = False
    return all_ok

def check_env_vars():
    required = {
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
    }
    optional = {
        "PINECONE_API_KEY": settings.PINECONE_API_KEY,
        "GCP_PROJECT_ID": settings.GCP_PROJECT_ID,
    }
    all_ok = True
    for name, value in required.items():
        if value:
            logger.info(f"[PASS] {name} is set ({value[:8]}...)")
        else:
            logger.error(f"[FAIL] {name} is NOT set: add it to your .env file")
            all_ok = False
    for name, value in optional.items():
        if value:
            logger.info(f"[PASS] {name} is set")
        else:
            logger.warning(f"[WARN] {name} is not set")
    return all_ok

def check_data_dirs():
    settings.create_data_dirs()
    dirs = [settings.DATA_DIR, settings.FASTF1_CACHE_DIR]
    all_ok = True
    for d in dirs:
        if d.exists():
            logger.info(f"[PASS] Directory exists: {d}")
        else:
            logger.error(f"[FAIL] Directory missing: {d}")
            all_ok = False
    return all_ok

def main():
    logger.info("F1 Race Intelligence System: Health Check")
    checks = [
        ("Python Version", check_python_version),
        ("Package Imports", check_imports),
        ("Environment Variables", check_env_vars),
        ("Data Directories", check_data_dirs),
    ]
    results = {}
    for name, check_fn in checks:
        logger.info(f"\n{name}")
        results[name] = check_fn()
    passed = sum(results.values())
    total = len(results)
    logger.info(f"Health Check Complete: {passed}/{total} checks passed")
    if passed == total:
        logger.success("All checks passed!")
    else:
        logger.warning("Some checks failed")
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)