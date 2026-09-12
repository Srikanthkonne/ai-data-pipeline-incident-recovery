import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    row_number,
    trim,
    upper,
)
from pyspark.sql.window import Window


BRONZE_PATH = "s3a://data-platform/bronze/transactions"
SILVER_PATH = "s3a://data-platform/silver/transactions"

MINIO_ENDPOINT = "http://minio:9000"


spark = (
    SparkSession.builder
    .appName("SilverTransactions")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# ---------------------------------------------------------
# MinIO / S3A configuration
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
    os.environ["MINIO_ROOT_USER"],
)

hadoop_conf.set(
    "fs.s3a.secret.key",
    os.environ["MINIO_ROOT_PASSWORD"],
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
# 1. Read Bronze
# ---------------------------------------------------------

bronze_df = spark.read.parquet(
    BRONZE_PATH
)

bronze_count = bronze_df.count()

print(
    f"Bronze row count: {bronze_count}"
)


# ---------------------------------------------------------
# 2. Normalize fields
# ---------------------------------------------------------

normalized_df = (
    bronze_df
    .withColumn(
        "transaction_id",
        trim(col("transaction_id")),
    )
    .withColumn(
        "customer_id",
        trim(col("customer_id")),
    )
    .withColumn(
        "order_id",
        trim(col("order_id")),
    )
    .withColumn(
        "payment_id",
        trim(col("payment_id")),
    )
    .withColumn(
        "status",
        upper(trim(col("status"))),
    )
    .withColumn(
        "payment_method",
        upper(trim(col("payment_method"))),
    )
)


# ---------------------------------------------------------
# 3. Remove malformed / unusable rows
# ---------------------------------------------------------

valid_df = (
    normalized_df

    # Required transaction identifier
    .filter(
        col("transaction_id").isNotNull()
        & (col("transaction_id") != "")
    )

    # Required customer identifier
    .filter(
        col("customer_id").isNotNull()
        & (col("customer_id") != "")
    )

    # Valid transaction amount
    .filter(
        col("amount").isNotNull()
        & (col("amount") > 0)
    )
)


# ---------------------------------------------------------
# 4. Deterministic transaction deduplication
# ---------------------------------------------------------

dedup_window = (
    Window
    .partitionBy("transaction_id")
    .orderBy(
        col("kafka_timestamp").desc(),
        col("kafka_offset").desc(),
        col("ingestion_timestamp").desc(),
    )
)

silver_df = (
    valid_df
    .withColumn(
        "_dedup_rank",
        row_number().over(
            dedup_window
        ),
    )
    .filter(
        col("_dedup_rank") == 1
    )
    .drop(
        "_dedup_rank"
    )
    .withColumn(
        "silver_processed_at",
        current_timestamp(),
    )
)


# ---------------------------------------------------------
# 5. Select Silver schema
# ---------------------------------------------------------

silver_df = silver_df.select(
    "transaction_id",
    "customer_id",
    "order_id",
    "payment_id",
    "amount",
    "payment_method",
    "status",
    "event_time",

    # Kafka traceability
    "kafka_key",
    "kafka_topic",
    "kafka_partition",
    "kafka_offset",
    "kafka_timestamp",

    # Processing metadata
    "ingestion_timestamp",
    "silver_processed_at",
)


silver_count = silver_df.count()

print(
    f"Silver row count: {silver_count}"
)

print(
    f"Rows removed during cleaning/deduplication: "
    f"{bronze_count - silver_count}"
)

print("\nSilver sample:")

silver_df.show(
    10,
    truncate=False,
)


# ---------------------------------------------------------
# 6. Write Silver
# ---------------------------------------------------------

(
    silver_df.write
    .mode("overwrite")
    .parquet(
        SILVER_PATH
    )
)

print(
    "\nSilver transactions written successfully."
)


spark.stop()