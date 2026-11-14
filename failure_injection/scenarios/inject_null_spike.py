import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    lit,
    when,
)


SILVER_PATH = "s3a://data-platform/silver/transactions"
BACKUP_PATH = "s3a://data-platform/failure-backups/null-spike/silver-transactions"
TEMP_PATH = "s3a://data-platform/failure-temp/null-spike/silver-transactions"

MINIO_ENDPOINT = "http://minio:9000"

NULL_TARGET_COLUMN = "payment_method"

# Deterministically target roughly 10% of rows.
INJECTION_MODULUS = 10

# Must exceed the Phase 3 detector threshold.
DETECTION_THRESHOLD = 0.05


def configure_s3a(spark):
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


def main():
    spark = (
        SparkSession.builder
        .appName("InjectNullSpike")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")
    configure_s3a(spark)

    hadoop_conf = (
        spark.sparkContext
        ._jsc
        .hadoopConfiguration()
    )

    Path = spark.sparkContext._jvm.org.apache.hadoop.fs.Path

    silver_path = Path(SILVER_PATH)
    backup_path = Path(BACKUP_PATH)
    temp_path = Path(TEMP_PATH)

    filesystem = silver_path.getFileSystem(hadoop_conf)

    silver_df = spark.read.parquet(SILVER_PATH)

    total_rows = silver_df.count()

    if total_rows == 0:
        raise RuntimeError(
            "Silver dataset is empty. Failure injection aborted."
        )

    original_nulls = (
        silver_df
        .filter(col(NULL_TARGET_COLUMN).isNull())
        .count()
    )

    print(f"Silver rows before injection: {total_rows}")
    print(
        f"{NULL_TARGET_COLUMN} nulls before injection: "
        f"{original_nulls}"
    )

    # Preserve the original clean Silver dataset.
    if filesystem.exists(backup_path):
        print(
            "Clean backup already exists. "
            "Existing backup will NOT be overwritten."
        )
    else:
        (
            silver_df.write
            .mode("errorifexists")
            .parquet(BACKUP_PATH)
        )

        print(
            f"Clean Silver backup created at: "
            f"{BACKUP_PATH}"
        )

    corrupted_df = silver_df.withColumn(
        NULL_TARGET_COLUMN,
        when(
            (col("kafka_offset") % INJECTION_MODULUS) == 0,
            lit(None).cast("string"),
        ).otherwise(
            col(NULL_TARGET_COLUMN)
        ),
    )

    corrupted_nulls = (
        corrupted_df
        .filter(col(NULL_TARGET_COLUMN).isNull())
        .count()
    )

    null_rate = corrupted_nulls / total_rows

    print(
        f"{NULL_TARGET_COLUMN} nulls after injection: "
        f"{corrupted_nulls}"
    )
    print(f"Injected null rate: {null_rate:.2%}")

    if null_rate <= DETECTION_THRESHOLD:
        raise RuntimeError(
            f"Injected null rate {null_rate:.2%} does not exceed "
            f"detector threshold {DETECTION_THRESHOLD:.2%}. "
            f"Silver was NOT modified."
        )

    # Write corrupted data separately before touching Silver.
    (
        corrupted_df.write
        .mode("overwrite")
        .parquet(TEMP_PATH)
    )

    if filesystem.exists(silver_path):
        filesystem.delete(silver_path, True)

    if not filesystem.rename(temp_path, silver_path):
        raise RuntimeError(
            "Unable to replace Silver dataset with injected dataset."
        )

    print("Null-spike failure injection completed successfully.")

    spark.stop()


if __name__ == "__main__":
    main()
