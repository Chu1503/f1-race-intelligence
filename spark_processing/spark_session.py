import sys, os
import pickle
import pyspark.serializers
pyspark.serializers.PICKLE_PROTOCOL = 4

import faulthandler
faulthandler.enable()

os.environ["HADOOP_HOME"] = r"C:\hadoop"
os.environ["PATH"] = r"C:\hadoop\bin;" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyspark.sql import SparkSession
from loguru import logger
from config import settings


def get_spark_session(app_name: str = None) -> SparkSession:
    name = app_name or settings.SPARK_APP_NAME

    spark = (
        SparkSession.builder
        .appName(name)
        .master(settings.SPARK_MASTER_URL)
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.default.parallelism", "4")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.execution.arrow.pyspark.enabled", "false")
        .config("spark.python.worker.reuse", "false")
        .config("spark.rpc.message.maxSize", "256")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")
    logger.info(f"SparkSession created: app={name} master={settings.SPARK_MASTER_URL}")
    return spark