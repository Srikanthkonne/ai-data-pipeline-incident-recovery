import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    count,
    sum as spark_sum,
    when,
)


BRONZE_PATH = "s3a://data-platform/bronze/transactions"
MINIO_ENDPOINT = "http://minio:9000"


def configure_minio(spark: SparkSession) -> None:
    """
    Configure Hadoop S3A so Spark can access the local
    MinIO object store.
    """

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


def validate_bronze(spark: SparkSession) -> None:
    """
    Validate the minimum Bronze data guarantees required
    for the Phase 1 acceptance test.
    """

    bronze_df = spark.read.parquet(
        BRONZE_PATH
    )

    metrics = (
        bronze_df
        .agg(
            count("*").alias(
                "total_rows"
            ),

            spark_sum(
                when(
                    col("transaction_id").isNull(),
                    1,
                ).otherwise(0)
            ).alias(
                "null_transaction_ids"
            ),

            spark_sum(
                when(
                    col("customer_id").isNull(),
                    1,
                ).otherwise(0)
            ).alias(
                "null_customer_ids"
            ),

            spark_sum(
                when(
                    col("kafka_offset").isNull(),
                    1,
                ).otherwise(0)
            ).alias(
                "null_kafka_offsets"
            ),
        )
        .collect()[0]
    )

    total_rows = metrics["total_rows"]
    null_transaction_ids = (
        metrics["null_transaction_ids"] or 0
    )
    null_customer_ids = (
        metrics["null_customer_ids"] or 0
    )
    null_kafka_offsets = (
        metrics["null_kafka_offsets"] or 0
    )

    print()
    print("=" * 55)
    print("BRONZE DATA VALIDATION")
    print("=" * 55)

    print(
        f"Total Bronze rows: {total_rows}"
    )

    print(
        "Null transaction IDs: "
        f"{null_transaction_ids}"
    )

    print(
        "Null customer IDs: "
        f"{null_customer_ids}"
    )

    print(
        "Null Kafka offsets: "
        f"{null_kafka_offsets}"
    )

    print("=" * 55)

    validation_errors = []

    if total_rows == 0:
        validation_errors.append(
            "Bronze dataset contains no rows."
        )

    if null_transaction_ids > 0:
        validation_errors.append(
            "Bronze contains null transaction IDs."
        )

    if null_customer_ids > 0:
        validation_errors.append(
            "Bronze contains null customer IDs."
        )

    if null_kafka_offsets > 0:
        validation_errors.append(
            "Bronze contains null Kafka offsets."
        )

    if validation_errors:
        print("Bronze validation: FAILED")

        for error in validation_errors:
            print(
                f"- {error}"
            )

        raise RuntimeError(
            "Bronze data validation failed."
        )

    print("Bronze validation: PASSED")
    print("=" * 55)
    print()


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("BronzeDataValidation")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel(
        "WARN"
    )

    try:
        configure_minio(
            spark
        )

        validate_bronze(
            spark
        )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()