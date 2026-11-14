import os

from pyspark.sql import SparkSession


SILVER_PATH = "s3a://data-platform/silver/transactions"

BACKUP_PATH = (
    "s3a://data-platform/"
    "failure-backups/schema-drift/silver-transactions"
)

TEMP_PATH = (
    "s3a://data-platform/"
    "failure-temp/schema-drift-restore/silver-transactions"
)

MINIO_ENDPOINT = "http://minio:9000"


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
    spark = (
        SparkSession.builder
        .appName("RestoreSchemaDrift")
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

    if not fs.exists(backup_path):
        raise FileNotFoundError(
            "Schema-drift backup does not exist."
        )

    backup_df = spark.read.parquet(
        BACKUP_PATH
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
        TEMP_PATH
    )

    if fs.exists(silver_path):
        fs.delete(
            silver_path,
            True,
        )

    restored = fs.rename(
        temp_path,
        silver_path,
    )

    if not restored:
        raise RuntimeError(
            "Failed to restore clean Silver dataset."
        )

    print(
        "Clean Silver schema restored successfully."
    )

    spark.stop()


if __name__ == "__main__":
    main()
