import json
import os
from datetime import datetime, timezone

from pyspark.sql import SparkSession


BRONZE_PATH = "s3a://data-platform/bronze/transactions"
MINIO_ENDPOINT = "http://minio:9000"

DATASET_NAMESPACE = "s3://data-platform"
DATASET_NAME = "bronze/transactions"

OUTPUT_PATH = (
    "/opt/spark/work-dir/evidence/"
    "bronze_schema.json"
)


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
        .appName("CaptureBronzeSchema")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")
    configure_s3a(spark)

    silver_df = spark.read.parquet(
        BRONZE_PATH
    )

    observed_schema = {
        column_name: data_type
        for column_name, data_type
        in silver_df.dtypes
    }

    evidence = {
        "namespace": DATASET_NAMESPACE,
        "name": DATASET_NAME,
        "source_path": BRONZE_PATH,
        "captured_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "schema": observed_schema,
    }

    os.makedirs(
        os.path.dirname(OUTPUT_PATH),
        exist_ok=True,
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            evidence,
            file,
            indent=2,
            sort_keys=True,
        )

    print("Bronze schema captured successfully.")
    print(f"Evidence path: {OUTPUT_PATH}")
    print(
        f"Observed columns: "
        f"{len(observed_schema)}"
    )

    for column_name, data_type in observed_schema.items():
        print(f"{column_name}: {data_type}")

    spark.stop()


if __name__ == "__main__":
    main()
