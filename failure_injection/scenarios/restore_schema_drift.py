import os

from pyspark.sql import SparkSession


DEFAULT_SILVER_PATH = (
    "s3a://data-platform/silver/transactions"
)

DEFAULT_BACKUP_PATH = (
    "s3a://data-platform/"
    "failure-backups/schema-drift/"
    "silver-transactions"
)

DEFAULT_TEMP_PATH = (
    "s3a://data-platform/"
    "failure-temp/schema-drift-restore/"
    "silver-transactions"
)

DEFAULT_MINIO_ENDPOINT = "http://minio:9000"


def _read_storage_config():
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

    backup_path = os.getenv(
        "RECOVERY_BACKUP_PATH",
        DEFAULT_BACKUP_PATH,
    ).strip()

    temp_path = os.getenv(
        "RECOVERY_TEMP_PATH",
        DEFAULT_TEMP_PATH,
    ).strip()

    if not silver_path:
        raise ValueError(
            "RECOVERY_SILVER_PATH must not be empty."
        )

    if not backup_path:
        raise ValueError(
            "RECOVERY_BACKUP_PATH must not be empty."
        )

    if not temp_path:
        raise ValueError(
            "RECOVERY_TEMP_PATH must not be empty."
        )

    return {
        "backend": backend,
        "silver_path": silver_path,
        "backup_path": backup_path,
        "temp_path": temp_path,
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

    # For aws-s3 we intentionally do not inject
    # static credentials or a custom endpoint.
    # EMR Serverless uses its execution role and
    # the native AWS S3 configuration.

    return hadoop_conf


def main():
    config = _read_storage_config()

    spark = (
        SparkSession.builder
        .appName("RestoreSchemaDrift")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    hadoop_conf = configure_storage(
        spark,
        backend=config["backend"],
    )

    jvm = spark.sparkContext._jvm

    silver_path = jvm.org.apache.hadoop.fs.Path(
        config["silver_path"]
    )

    backup_path = jvm.org.apache.hadoop.fs.Path(
        config["backup_path"]
    )

    temp_path = jvm.org.apache.hadoop.fs.Path(
        config["temp_path"]
    )

    silver_fs = silver_path.getFileSystem(
        hadoop_conf
    )

    backup_fs = backup_path.getFileSystem(
        hadoop_conf
    )

    print(
        "Recovery storage backend: "
        f"{config['backend']}"
    )

    print(
        "Silver path: "
        f"{config['silver_path']}"
    )

    print(
        "Backup path: "
        f"{config['backup_path']}"
    )

    if not backup_fs.exists(
        backup_path
    ):
        raise FileNotFoundError(
            "Schema-drift backup does not exist: "
            f"{config['backup_path']}"
        )

    backup_df = spark.read.parquet(
        config["backup_path"]
    )

    print(
        f"Backup columns: "
        f"{len(backup_df.columns)}"
    )

    print("Backup schema:")

    backup_df.printSchema()

    backup_df.write.mode(
        "overwrite"
    ).parquet(
        config["temp_path"]
    )

    if silver_fs.exists(
        silver_path
    ):
        silver_fs.delete(
            silver_path,
            True,
        )

    restored = silver_fs.rename(
        temp_path,
        silver_path,
    )

    if not restored:
        raise RuntimeError(
            "Failed to restore clean "
            "Silver dataset."
        )

    print(
        "Clean Silver schema restored successfully."
    )

    spark.stop()


if __name__ == "__main__":
    main()
