import json
import os

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from pyspark.sql import SparkSession


DEFAULT_SILVER_PATH = (
    "s3a://data-platform/silver/transactions"
)

DEFAULT_MINIO_ENDPOINT = "http://minio:9000"

DEFAULT_DATASET_NAMESPACE = "s3://data-platform"

DEFAULT_DATASET_NAME = "silver/transactions"

DEFAULT_OUTPUT_PATH = (
    "/opt/spark/work-dir/evidence/"
    "silver_schema.json"
)


def _read_config():
    backend = os.getenv(
        "RECOVERY_STORAGE_BACKEND",
        "minio",
    ).strip().lower()

    if backend not in {
        "minio",
        "aws-s3",
    }:
        raise ValueError(
            "RECOVERY_STORAGE_BACKEND must be "
            "minio or aws-s3."
        )

    silver_path = os.getenv(
        "RECOVERY_SILVER_PATH",
        DEFAULT_SILVER_PATH,
    ).strip()

    evidence_path = os.getenv(
        "RECOVERY_SCHEMA_EVIDENCE_PATH",
        DEFAULT_OUTPUT_PATH,
    ).strip()

    namespace = os.getenv(
        "RECOVERY_DATASET_NAMESPACE",
        DEFAULT_DATASET_NAMESPACE,
    ).strip()

    dataset_name = os.getenv(
        "RECOVERY_DATASET_NAME",
        DEFAULT_DATASET_NAME,
    ).strip()

    if not silver_path:
        raise ValueError(
            "RECOVERY_SILVER_PATH must not be empty."
        )

    if not evidence_path:
        raise ValueError(
            "RECOVERY_SCHEMA_EVIDENCE_PATH "
            "must not be empty."
        )

    return {
        "backend": backend,
        "silver_path": silver_path,
        "evidence_path": evidence_path,
        "namespace": namespace,
        "dataset_name": dataset_name,
    }


def configure_storage(
    spark,
    *,
    backend,
):
    hadoop_conf = (
        spark.sparkContext
        ._jsc
        .hadoopConfiguration()
    )

    if backend == "minio":
        endpoint = os.getenv(
            "MINIO_ENDPOINT",
            DEFAULT_MINIO_ENDPOINT,
        ).strip()

        hadoop_conf.set(
            "fs.s3a.endpoint",
            endpoint,
        )

        hadoop_conf.set(
            "fs.s3a.access.key",
            os.environ["MINIO_ROOT_USER"],
        )

        hadoop_conf.set(
            "fs.s3a.secret.key",
            os.environ[
                "MINIO_ROOT_PASSWORD"
            ],
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
            (
                "org.apache.hadoop.fs.s3a."
                "S3AFileSystem"
            ),
        )

    return hadoop_conf


def _is_remote_path(path: str) -> bool:
    return path.startswith(
        (
            "s3://",
            "s3a://",
        )
    )


def write_evidence(
    *,
    spark,
    hadoop_conf,
    output_path: str,
    evidence: dict,
) -> None:
    content = json.dumps(
        evidence,
        indent=2,
        sort_keys=True,
    )

    if not _is_remote_path(output_path):
        local_path = Path(output_path)

        local_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        local_path.write_text(
            content,
            encoding="utf-8",
        )

        return

    jvm = spark.sparkContext._jvm

    remote_path = (
        jvm.org.apache.hadoop.fs.Path(
            output_path
        )
    )

    filesystem = remote_path.getFileSystem(
        hadoop_conf
    )

    parent = remote_path.getParent()

    if parent is not None:
        filesystem.mkdirs(parent)

    output_stream = filesystem.create(
        remote_path,
        True,
    )

    writer = jvm.java.io.OutputStreamWriter(
        output_stream,
        "UTF-8",
    )

    try:
        writer.write(content)
        writer.flush()

    finally:
        writer.close()


def main():
    config = _read_config()

    spark = (
        SparkSession.builder
        .appName("CaptureSilverSchema")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel(
        "WARN"
    )

    try:
        hadoop_conf = configure_storage(
            spark,
            backend=config["backend"],
        )

        jvm = spark.sparkContext._jvm

        silver_path = (
            jvm.org.apache.hadoop.fs.Path(
                config["silver_path"]
            )
        )

        filesystem = (
            silver_path.getFileSystem(
                hadoop_conf
            )
        )

        if not filesystem.exists(
            silver_path
        ):
            evidence = {
                "namespace":
                    config["namespace"],
                "name":
                    config["dataset_name"],
                "source_path":
                    config["silver_path"],
                "captured_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
                "dataset_exists":
                    False,
                "capture_status":
                    "MISSING_DATASET",
                "schema":
                    {},
            }

            write_evidence(
                spark=spark,
                hadoop_conf=hadoop_conf,
                output_path=(
                    config["evidence_path"]
                ),
                evidence=evidence,
            )

            print(
                "Silver dataset does not exist."
            )

            print(
                "Evidence path: "
                f"{config['evidence_path']}"
            )

            return

        silver_df = spark.read.parquet(
            config["silver_path"]
        )

        observed_schema = {
            column_name: data_type
            for column_name, data_type
            in silver_df.dtypes
        }

        evidence = {
            "namespace":
                config["namespace"],
            "name":
                config["dataset_name"],
            "source_path":
                config["silver_path"],
            "captured_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "dataset_exists":
                True,
            "capture_status":
                "CAPTURED",
            "schema":
                observed_schema,
        }

        write_evidence(
            spark=spark,
            hadoop_conf=hadoop_conf,
            output_path=(
                config["evidence_path"]
            ),
            evidence=evidence,
        )

        print(
            "Silver schema captured "
            "successfully."
        )

        print(
            "Evidence path: "
            f"{config['evidence_path']}"
        )

        print(
            "Observed columns: "
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
