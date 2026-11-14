import json
import os

from datetime import datetime, timezone

from typing import Dict

from pyspark.sql import SparkSession


SILVER_PATH = (
    "s3a://data-platform/silver/transactions"
)

MINIO_ENDPOINT = "http://minio:9000"

DATASET_NAMESPACE = "s3://data-platform"

DATASET_NAME = "silver/transactions"

OUTPUT_PATH = (
    "/opt/spark/work-dir/evidence/"
    "silver_schema.json"
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

    return hadoop_conf


def write_evidence(
    *,
    dataset_exists: bool,
    capture_status: str,
    observed_schema: Dict[str, str],
) -> None:

    evidence = {
        "namespace":
            DATASET_NAMESPACE,
        "name":
            DATASET_NAME,
        "source_path":
            SILVER_PATH,
        "captured_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "dataset_exists":
            dataset_exists,
        "capture_status":
            capture_status,
        "schema":
            observed_schema,
    }

    os.makedirs(
        os.path.dirname(
            OUTPUT_PATH
        ),
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


def main():
    spark = (
        SparkSession.builder
        .appName("CaptureSilverSchema")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel(
        "WARN"
    )

    try:
        hadoop_conf = configure_s3a(
            spark
        )

        jvm = spark.sparkContext._jvm

        silver_path = (
            jvm.org.apache.hadoop.fs.Path(
                SILVER_PATH
            )
        )

        fs = silver_path.getFileSystem(
            hadoop_conf
        )

        if not fs.exists(
            silver_path
        ):
            write_evidence(
                dataset_exists=False,
                capture_status=
                    "MISSING_DATASET",
                observed_schema={},
            )

            print(
                "Silver dataset does not exist."
            )

            print(
                f"Evidence path: "
                f"{OUTPUT_PATH}"
            )

            return

        silver_df = spark.read.parquet(
            SILVER_PATH
        )

        observed_schema = {
            column_name:
                data_type
            for column_name, data_type
            in silver_df.dtypes
        }

        write_evidence(
            dataset_exists=True,
            capture_status="CAPTURED",
            observed_schema=
                observed_schema,
        )

        print(
            "Silver schema captured "
            "successfully."
        )

        print(
            f"Evidence path: "
            f"{OUTPUT_PATH}"
        )

        print(
            f"Observed columns: "
            f"{len(observed_schema)}"
        )

        for (
            column_name,
            data_type,
        ) in observed_schema.items():
            print(
                f"{column_name}: "
                f"{data_type}"
            )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
