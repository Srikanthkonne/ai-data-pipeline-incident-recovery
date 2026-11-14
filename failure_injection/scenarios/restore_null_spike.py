import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col


SILVER_PATH = "s3a://data-platform/silver/transactions"
BACKUP_PATH = "s3a://data-platform/failure-backups/null-spike/silver-transactions"
TEMP_PATH = "s3a://data-platform/failure-temp/null-spike/restore-silver-transactions"

MINIO_ENDPOINT = "http://minio:9000"
NULL_TARGET_COLUMN = "payment_method"


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
        .appName("RestoreNullSpike")
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

    if not filesystem.exists(backup_path):
        raise RuntimeError(
            "Clean null-spike backup does not exist."
        )

    backup_df = spark.read.parquet(BACKUP_PATH)

    total_rows = backup_df.count()

    payment_method_nulls = (
        backup_df
        .filter(col(NULL_TARGET_COLUMN).isNull())
        .count()
    )

    print(f"Backup rows: {total_rows}")
    print(
        f"{NULL_TARGET_COLUMN} nulls in backup: "
        f"{payment_method_nulls}"
    )

    (
        backup_df.write
        .mode("overwrite")
        .parquet(TEMP_PATH)
    )

    if filesystem.exists(silver_path):
        filesystem.delete(silver_path, True)

    if not filesystem.rename(temp_path, silver_path):
        raise RuntimeError(
            "Unable to restore Silver from clean backup."
        )

    print("Clean Silver dataset restored successfully.")

    spark.stop()


if __name__ == "__main__":
    main()
