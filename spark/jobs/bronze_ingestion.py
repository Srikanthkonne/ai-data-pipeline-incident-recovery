import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    from_json,
    to_timestamp,
)

from schemas.transaction_schema import TRANSACTION_SCHEMA


KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"
KAFKA_TOPIC = "transactions"

BRONZE_PATH = "s3a://data-platform/bronze/transactions"

CHECKPOINT_PATH = (
    "s3a://data-platform/checkpoints/transactions"
)

MINIO_ENDPOINT = "http://minio:9000"

MINIO_ACCESS_KEY = os.environ["MINIO_ROOT_USER"]
MINIO_SECRET_KEY = os.environ["MINIO_ROOT_PASSWORD"]


spark = (
    SparkSession.builder
    .appName("TransactionBronzeIngestion")
    .getOrCreate()
)


spark.sparkContext.setLogLevel("WARN")


# ---------------------------------------------------------
# Configure MinIO through Hadoop S3A
# ---------------------------------------------------------

hadoop_conf = (
    spark.sparkContext
    ._jsc
    .hadoopConfiguration()
)

hadoop_conf.set(
    "fs.s3a.endpoint",
    MINIO_ENDPOINT,
)

hadoop_conf.set(
    "fs.s3a.access.key",
    MINIO_ACCESS_KEY,
)

hadoop_conf.set(
    "fs.s3a.secret.key",
    MINIO_SECRET_KEY,
)

hadoop_conf.set(
    "fs.s3a.path.style.access",
    "true",
)

hadoop_conf.set(
    "fs.s3a.connection.ssl.enabled",
    "false",
)

hadoop_conf.set(
    "fs.s3a.impl",
    "org.apache.hadoop.fs.s3a.S3AFileSystem",
)


# ---------------------------------------------------------
# 1. Read raw Kafka messages
# ---------------------------------------------------------

kafka_df = (
    spark.readStream
    .format("kafka")
    .option(
        "kafka.bootstrap.servers",
        KAFKA_BOOTSTRAP_SERVERS,
    )
    .option(
        "subscribe",
        KAFKA_TOPIC,
    )
    .option(
        "startingOffsets",
        "latest",
    )
    .load()
)


# ---------------------------------------------------------
# 2. Convert Kafka binary values to strings
# ---------------------------------------------------------

raw_df = kafka_df.select(
    col("key")
    .cast("string")
    .alias("kafka_key"),

    col("value")
    .cast("string")
    .alias("raw_value"),

    col("topic")
    .alias("kafka_topic"),

    col("partition")
    .alias("kafka_partition"),

    col("offset")
    .alias("kafka_offset"),

    col("timestamp")
    .alias("kafka_timestamp"),
)


# ---------------------------------------------------------
# 3. Parse JSON using explicit schema
# ---------------------------------------------------------

parsed_df = raw_df.withColumn(
    "transaction",
    from_json(
        col("raw_value"),
        TRANSACTION_SCHEMA,
    ),
)


# ---------------------------------------------------------
# 4. Flatten transaction fields
# ---------------------------------------------------------

transactions_df = parsed_df.select(
    col("transaction.transaction_id"),

    col("transaction.customer_id"),

    col("transaction.order_id"),

    col("transaction.payment_id"),

    col("transaction.amount"),

    col("transaction.payment_method"),

    col("transaction.status"),

    to_timestamp(
        col("transaction.event_time")
    ).alias("event_time"),

    col("kafka_key"),

    col("kafka_topic"),

    col("kafka_partition"),

    col("kafka_offset"),

    col("kafka_timestamp"),

    current_timestamp().alias(
        "ingestion_timestamp"
    ),
)


# ---------------------------------------------------------
# 5. Write Bronze data to MinIO
# ---------------------------------------------------------

query = (
    transactions_df.writeStream
    .format("parquet")
    .outputMode("append")
    .option(
        "path",
        BRONZE_PATH,
    )
    .option(
        "checkpointLocation",
        CHECKPOINT_PATH,
    )
    .start()
)


query.awaitTermination()