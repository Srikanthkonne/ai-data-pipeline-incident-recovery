import json
import os

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit


STORAGE_BACKEND = os.getenv(
    "RECOVERY_STORAGE_BACKEND",
    "minio",
).strip().lower()

SILVER_PATH = os.getenv(
    "RECOVERY_SILVER_PATH",
    "s3a://data-platform/silver/transactions",
)

BACKUP_PATH = os.getenv(
    "RECOVERY_BACKUP_PATH",
    (
        "s3a://data-platform/"
        "failure-backups/schema-drift/"
        "silver-transactions"
    ),
)

TEMP_PATH = os.getenv(
    "RECOVERY_TEMP_PATH",
    (
        "s3a://data-platform/"
        "failure-temp/schema-drift-restore/"
        "silver-transactions"
    ),
)

DATASET_NAME = os.getenv(
    "RECOVERY_DATASET_NAME",
    "silver/transactions",
)

MINIO_ENDPOINT = os.getenv(
    "MINIO_ENDPOINT",
    "http://minio:9000",
)

DRIFT_COLUMN = os.getenv(
    "SCHEMA_DRIFT_COLUMN",
    "currency_code",
)

DRIFT_VALUE = os.getenv(
    "SCHEMA_DRIFT_VALUE",
    "USD",
)

EXECUTION_ID = os.getenv(
    "SCHEMA_DRIFT_EXECUTION_ID",
)

PROVENANCE_DIR = Path(
    os.getenv(
        "RECOVERY_PROVENANCE_DIR",
        (
            "/opt/spark/work-dir/evidence/"
            "failure_injections"
        ),
    )
)

PROVENANCE_URI_PREFIX = os.getenv(
    "RECOVERY_PROVENANCE_URI_PREFIX",
)


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def configure_storage(spark):
    hadoop_conf = (
        spark.sparkContext
        ._jsc
        .hadoopConfiguration()
    )

    if STORAGE_BACKEND == "minio":
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
            (
                "org.apache.hadoop.fs.s3a."
                "S3AFileSystem"
            ),
        )

    elif STORAGE_BACKEND == "aws-s3":
        # EMR Serverless uses its runtime IAM role and
        # native S3 filesystem configuration.
        pass

    else:
        raise ValueError(
            "Unsupported RECOVERY_STORAGE_BACKEND: "
            f"{STORAGE_BACKEND}"
        )

    return hadoop_conf


def write_provenance(
    *,
    execution_id,
    started_at,
    status,
    hadoop_conf,
    jvm,
    **extra,
):
    record = {
        "execution_id": execution_id,
        "scenario": "SCHEMA_DRIFT",
        "status": status,
        "started_at": started_at,
        "recorded_at": utc_now(),
        "storage_backend": STORAGE_BACKEND,
        "target_dataset": DATASET_NAME,
        "target_path": SILVER_PATH,
        "backup_path": BACKUP_PATH,
        "injected_column": DRIFT_COLUMN,
        "injected_value": DRIFT_VALUE,
        **extra,
    }

    payload = json.dumps(
        record,
        indent=2,
        sort_keys=True,
    )

    filename = (
        f"schema_drift_{execution_id}.json"
    )

    if PROVENANCE_URI_PREFIX:
        uri = (
            PROVENANCE_URI_PREFIX.rstrip("/")
            + "/"
            + filename
        )

        output_path = (
            jvm.org.apache.hadoop.fs.Path(
                uri
            )
        )

        fs = output_path.getFileSystem(
            hadoop_conf
        )

        parent = output_path.getParent()

        if (
            parent is not None
            and not fs.exists(parent)
        ):
            fs.mkdirs(parent)

        stream = fs.create(
            output_path,
            True,
        )

        writer = (
            jvm.java.io.OutputStreamWriter(
                stream,
                "UTF-8",
            )
        )

        try:
            writer.write(payload)
        finally:
            writer.close()

        return uri

    PROVENANCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        PROVENANCE_DIR
        / filename
    )

    output_path.write_text(
        payload,
        encoding="utf-8",
    )

    return str(output_path)


def main():
    execution_id = (
        EXECUTION_ID
        or str(uuid4())
    )

    started_at = utc_now()

    spark = (
        SparkSession.builder
        .appName("InjectSchemaDrift")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel(
        "WARN"
    )

    try:
        hadoop_conf = configure_storage(
            spark
        )

        jvm = spark.sparkContext._jvm

        silver_path = (
            jvm.org.apache.hadoop.fs.Path(
                SILVER_PATH
            )
        )

        backup_path = (
            jvm.org.apache.hadoop.fs.Path(
                BACKUP_PATH
            )
        )

        temp_path = (
            jvm.org.apache.hadoop.fs.Path(
                TEMP_PATH
            )
        )

        fs = silver_path.getFileSystem(
            hadoop_conf
        )

        silver_df = spark.read.parquet(
            SILVER_PATH
        )

        print(
            "Storage backend: "
            f"{STORAGE_BACKEND}"
        )

        print(
            "Silver path: "
            f"{SILVER_PATH}"
        )

        print(
            "Execution ID: "
            f"{execution_id}"
        )

        print(
            "Silver columns before injection: "
            f"{len(silver_df.columns)}"
        )

        print(
            "Schema before injection:"
        )

        silver_df.printSchema()

        if DRIFT_COLUMN in silver_df.columns:
            raise ValueError(
                "Schema drift column already exists "
                f"in Silver: {DRIFT_COLUMN}"
            )

        if not fs.exists(backup_path):
            silver_df.write.mode(
                "overwrite"
            ).parquet(
                BACKUP_PATH
            )

            print(
                "Clean Silver backup created."
            )

        else:
            print(
                "Existing clean schema-drift "
                "backup preserved."
            )

        drifted_df = (
            silver_df.withColumn(
                DRIFT_COLUMN,
                lit(DRIFT_VALUE),
            )
        )

        print(
            "Silver columns after injection: "
            f"{len(drifted_df.columns)}"
        )

        print(
            "Schema after injection:"
        )

        drifted_df.printSchema()

        if (
            DRIFT_COLUMN
            not in drifted_df.columns
        ):
            raise ValueError(
                "Schema drift injection failed."
            )

        drifted_df.write.mode(
            "overwrite"
        ).parquet(
            TEMP_PATH
        )

        if fs.exists(silver_path):
            fs.delete(
                silver_path,
                True,
            )

        renamed = fs.rename(
            temp_path,
            silver_path,
        )

        if not renamed:
            raise RuntimeError(
                "Failed to replace Silver with "
                "schema-drifted dataset."
            )

        provenance_path = (
            write_provenance(
                execution_id=execution_id,
                started_at=started_at,
                status="COMPLETED",
                hadoop_conf=hadoop_conf,
                jvm=jvm,
                completed_at=utc_now(),
                columns_before=len(
                    silver_df.columns
                ),
                columns_after=len(
                    drifted_df.columns
                ),
            )
        )

        print(
            "Schema drift injected "
            "successfully."
        )

        print(
            "Runtime provenance: "
            f"{provenance_path}"
        )

        print(
            "Added unexpected column: "
            f"{DRIFT_COLUMN}"
        )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
