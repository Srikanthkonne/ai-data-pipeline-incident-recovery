import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col


SILVER_PATH = "s3a://data-platform/silver/transactions"

MINIO_ENDPOINT = "http://minio:9000"


spark = (
    SparkSession.builder
    .appName("ValidateSilverTransactions")
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
# Read Silver
# ---------------------------------------------------------

silver_df = spark.read.parquet(
    SILVER_PATH
)


# ---------------------------------------------------------
# Validation checks
# ---------------------------------------------------------

total_rows = silver_df.count()

null_transaction_ids = (
    silver_df
    .filter(
        col("transaction_id").isNull()
        | (col("transaction_id") == "")
    )
    .count()
)

null_customer_ids = (
    silver_df
    .filter(
        col("customer_id").isNull()
        | (col("customer_id") == "")
    )
    .count()
)

invalid_amounts = (
    silver_df
    .filter(
        col("amount").isNull()
        | (col("amount") <= 0)
    )
    .count()
)

duplicate_transaction_ids = (
    silver_df
    .groupBy("transaction_id")
    .count()
    .filter(
        col("count") > 1
    )
    .count()
)


# ---------------------------------------------------------
# Results
# ---------------------------------------------------------

print(f"Silver rows: {total_rows}")
print(
    f"Null/blank transaction IDs: "
    f"{null_transaction_ids}"
)
print(
    f"Null/blank customer IDs: "
    f"{null_customer_ids}"
)
print(
    f"Invalid amounts: "
    f"{invalid_amounts}"
)
print(
    f"Duplicate transaction IDs: "
    f"{duplicate_transaction_ids}"
)


# ---------------------------------------------------------
# Fail validation if Silver is not trustworthy
# ---------------------------------------------------------

if total_rows == 0:
    raise ValueError(
        "Silver validation FAILED: dataset is empty."
    )

if null_transaction_ids > 0:
    raise ValueError(
        "Silver validation FAILED: "
        "invalid transaction IDs found."
    )

if null_customer_ids > 0:
    raise ValueError(
        "Silver validation FAILED: "
        "invalid customer IDs found."
    )

if invalid_amounts > 0:
    raise ValueError(
        "Silver validation FAILED: "
        "invalid amounts found."
    )

if duplicate_transaction_ids > 0:
    raise ValueError(
        "Silver validation FAILED: "
        "duplicate transaction IDs found."
    )


print("\nSilver validation: PASSED")


spark.stop()