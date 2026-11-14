import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit


SILVER_PATH = "s3a://data-platform/silver/transactions"

BACKUP_PATH = (
    "s3a://data-platform/"
    "failure-backups/schema-drift/silver-transactions"
)

TEMP_PATH = (
    "s3a://data-platform/"
    "failure-temp/schema-drift/silver-transactions"
)

MINIO_ENDPOINT = "http://minio:9000"

DRIFT_COLUMN = os.getenv(
    "SCHEMA_DRIFT_COLUMN",
    "currency_code",
)

DRIFT_VALUE = os.getenv(
    "SCHEMA_DRIFT_VALUE",
    "USD",
)

PROVENANCE_DIR = Path(
    "/opt/spark/work-dir/evidence/"
    "failure_injections"
)


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def write_provenance(
    execution_id,
    started_at,
    status,
    **extra,
):
    PROVENANCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "execution_id": execution_id,
        "scenario": "SCHEMA_DRIFT",
        "status": status,
        "started_at": started_at,
        "recorded_at": utc_now(),
        "target_dataset":
            "silver/transactions",
        "target_path":
            SILVER_PATH,
        "backup_path":
            BACKUP_PATH,
        "injected_column":
            DRIFT_COLUMN,
        "injected_value":
            DRIFT_VALUE,
        **extra,
    }

    output_path = (
        PROVENANCE_DIR
        / f"schema_drift_{execution_id}.json"
    )

    output_path.write_text(
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
    )

    return output_path


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


def main():

    execution_id = str(
        uuid4()
    )
    started_at = utc_now()

    spark = (
        SparkSession.builder
        .appName("InjectSchemaDrift")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    hadoop_conf = configure_s3a(spark)

    jvm = spark.sparkContext._jvm

    silver_path = jvm.org.apache.hadoop.fs.Path(
        SILVER_PATH
    )
    backup_path = jvm.org.apache.hadoop.fs.Path(
        BACKUP_PATH
    )
    temp_path = jvm.org.apache.hadoop.fs.Path(
        TEMP_PATH
    )

    fs = silver_path.getFileSystem(
        hadoop_conf
    )

    silver_df = spark.read.parquet(
        SILVER_PATH
    )

    print(
        f"Silver columns before injection: "
        f"{len(silver_df.columns)}"
    )

    print("Schema before injection:")
    silver_df.printSchema()

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
            "Existing clean schema-drift backup preserved."
        )

    drifted_df = silver_df.withColumn(
        DRIFT_COLUMN,
        lit(DRIFT_VALUE),
    )

    print(
        f"Silver columns after injection: "
        f"{len(drifted_df.columns)}"
    )

    print("Schema after injection:")
    drifted_df.printSchema()

    if DRIFT_COLUMN not in drifted_df.columns:
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

    provenance_path = write_provenance(
        execution_id=execution_id,
        started_at=started_at,
        status="COMPLETED",
        completed_at=utc_now(),
        columns_before=len(
            silver_df.columns
        ),
        columns_after=len(
            drifted_df.columns
        ),
    )

    print(
        "Schema drift injected successfully."
    )

    print(
        f"Runtime provenance: "
        f"{provenance_path}"
    )
    print(
        f"Added unexpected column: "
        f"{DRIFT_COLUMN}"
    )

    spark.stop()


if __name__ == "__main__":
    main()
