
# schemas for all Kafka message types.
from pyspark.sql.types import (
    StructType, StructField,
    IntegerType, FloatType, StringType, BooleanType, TimestampType
)


LAP_DATA_SCHEMA = StructType([
    StructField("session_key",     IntegerType(), True),
    StructField("driver_number",   IntegerType(), True),
    StructField("lap_number",      IntegerType(), True),
    StructField("lap_duration",    FloatType(),   True),
    StructField("sector_1_time",   FloatType(),   True),
    StructField("sector_2_time",   FloatType(),   True),
    StructField("sector_3_time",   FloatType(),   True),
    StructField("tyre_compound",   StringType(),  True),
    StructField("tyre_age_laps",   IntegerType(), True),
    StructField("is_pit_out_lap",  BooleanType(), True),
    StructField("is_pit_in_lap",   BooleanType(), True),
    StructField("timestamp",       StringType(),  True),
    StructField("source",          StringType(),  True),
])

PIT_STOP_SCHEMA = StructType([
    StructField("session_key",        IntegerType(), True),
    StructField("driver_number",      IntegerType(), True),
    StructField("lap_number",         IntegerType(), True),
    StructField("pit_duration",       FloatType(),   True),
    StructField("tyre_compound_new",  StringType(),  True),
    StructField("timestamp",          StringType(),  True),
    StructField("source",             StringType(),  True),
])

POSITION_SCHEMA = StructType([
    StructField("session_key",    IntegerType(), True),
    StructField("driver_number",  IntegerType(), True),
    StructField("position",       IntegerType(), True),
    StructField("gap_to_leader",  FloatType(),   True),
    StructField("interval",       FloatType(),   True),
    StructField("timestamp",      StringType(),  True),
    StructField("source",         StringType(),  True),
])