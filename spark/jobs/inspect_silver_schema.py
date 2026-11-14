import os

from pyspark.sql import SparkSession


SILVER_PATH = "s3a://data-platform/silver/transactions"
MINIO_ENDPOINT = "http://minio:9000"


spark = (
    SparkSession.builder
    .appName("InspectSilverSchema")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

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

silver_df = spark.read.parquet(
    SILVER_PATH
)

print("\n" + "=" * 70)
print("CURRENT HEALTHY SILVER SCHEMA")
print("=" * 70)

silver_df.printSchema()

print("\nSilver dtypes:")
for column_name, data_type in silver_df.dtypes:
    print(f"{column_name}: {data_type}")

spark.stop()
