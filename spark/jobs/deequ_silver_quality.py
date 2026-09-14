import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    concat,
    current_timestamp,
    lit,
    when,
)

from pydeequ.checks import Check, CheckLevel
from pydeequ.verification import VerificationResult, VerificationSuite


SILVER_PATH = "s3a://data-platform/silver/transactions"
MINIO_ENDPOINT = "http://minio:9000"

DATASET_NAME = "silver.transactions"
DQ_TABLE = "public.data_quality_results"


# ---------------------------------------------------------
# Create Spark session
# ---------------------------------------------------------

def create_spark_session():
    minio_access_key = os.environ["MINIO_ROOT_USER"]
    minio_secret_key = os.environ["MINIO_ROOT_PASSWORD"]

    spark = (
        SparkSession.builder
        .appName("SilverTransactionsDeequQuality")
        .config(
            "spark.hadoop.fs.s3a.endpoint",
            MINIO_ENDPOINT,
        )
        .config(
            "spark.hadoop.fs.s3a.access.key",
            minio_access_key,
        )
        .config(
            "spark.hadoop.fs.s3a.secret.key",
            minio_secret_key,
        )
        .config(
            "spark.hadoop.fs.s3a.path.style.access",
            "true",
        )
        .config(
            "spark.hadoop.fs.s3a.connection.ssl.enabled",
            "false",
        )
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    return spark


# ---------------------------------------------------------
# Run Deequ quality checks
# ---------------------------------------------------------

def run_quality_checks(spark, transactions_df):
    check = (
        Check(
            spark,
            CheckLevel.Error,
            "silver_transactions_quality",
        )

        .isComplete(
            "transaction_id"
        )

        .isComplete(
            "customer_id"
        )

        .isUnique(
            "transaction_id"
        )

        .satisfies(
            "amount > 0",
            "amount_positive",
        )

        .isComplete(
            "status"
        )

        .isContainedIn(
            "status",
            [
                "SUCCESS",
                "FAILED",
                "PENDING",
            ],
        )

        .isComplete(
            "payment_method"
        )

        .isContainedIn(
            "payment_method",
            [
                "APPLE_PAY",
                "CREDIT_CARD",
                "DEBIT_CARD",
                "PAYPAL",
            ],
        )
    )

    return (
        VerificationSuite(spark)
        .onData(transactions_df)
        .addCheck(check)
        .run()
    )


# ---------------------------------------------------------
# Convert Deequ metrics into metadata format
# ---------------------------------------------------------

def prepare_dq_results(metrics_df):
    """
    Convert Deequ numeric metrics into the schema used by
    public.data_quality_results.

    For the current Silver rules, every metric is expected
    to equal 1.0.
    """

    return (
        metrics_df
        .select(
            lit(DATASET_NAME).alias(
                "dataset_name"
            ),

            col("instance").alias(
                "check_name"
            ),

            col("name").alias(
                "metric_name"
            ),

            col("value")
            .cast("double")
            .alias(
                "metric_value"
            ),

            when(
                col("value") == 1.0,
                lit("Success"),
            )
            .otherwise(
                lit("Failure")
            )
            .alias(
                "status"
            ),

            concat(
                lit("Deequ entity="),
                col("entity"),
                lit(
                    "; expected metric value=1.0"
                ),
            ).alias(
                "details"
            ),

            current_timestamp().alias(
                "run_timestamp"
            ),
        )
    )


# ---------------------------------------------------------
# Persist results to PostgreSQL
# ---------------------------------------------------------

def persist_dq_results(dq_results_df):
    postgres_host = os.environ["POSTGRES_HOST"]
    postgres_port = os.environ["POSTGRES_PORT"]
    postgres_db = os.environ["POSTGRES_DB"]
    postgres_user = os.environ["POSTGRES_USER"]
    postgres_password = os.environ["POSTGRES_PASSWORD"]

    jdbc_url = (
        f"jdbc:postgresql://"
        f"{postgres_host}:"
        f"{postgres_port}/"
        f"{postgres_db}"
    )

    (
        dq_results_df
        .write
        .format("jdbc")
        .option(
            "url",
            jdbc_url,
        )
        .option(
            "dbtable",
            DQ_TABLE,
        )
        .option(
            "user",
            postgres_user,
        )
        .option(
            "password",
            postgres_password,
        )
        .option(
            "driver",
            "org.postgresql.Driver",
        )
        .mode("append")
        .save()
    )

    print(
        f"DQ results persisted to PostgreSQL table: "
        f"{DQ_TABLE}"
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    spark = create_spark_session()

    try:
        print("=" * 70)
        print("DEEQU SILVER TRANSACTIONS DATA QUALITY")
        print("=" * 70)

        # -------------------------------------------------
        # Read Silver
        # -------------------------------------------------

        transactions_df = spark.read.parquet(
            SILVER_PATH
        )

        row_count = transactions_df.count()

        print(
            f"Silver dataset: {SILVER_PATH}"
        )

        print(
            f"Silver rows: {row_count}"
        )

        print()

        # -------------------------------------------------
        # Run Deequ
        # -------------------------------------------------

        verification_result = run_quality_checks(
            spark,
            transactions_df,
        )

        # -------------------------------------------------
        # Constraint-level results
        # -------------------------------------------------

        results_json = VerificationResult.checkResultsAsJson(
            spark,
            verification_result,
        )
        results_df = spark.createDataFrame(results_json)

        print("=" * 70)
        print("DEEQU CHECK RESULTS")
        print("=" * 70)

        results_df.show(
            truncate=False,
        )

        # -------------------------------------------------
        # Numeric Deequ metrics
        # -------------------------------------------------

        metrics_json = VerificationResult.successMetricsAsJson(
            spark,
            verification_result,
        )
        metrics_df = spark.createDataFrame(metrics_json)

        print("=" * 70)
        print("DEEQU QUALITY METRICS")
        print("=" * 70)

        metrics_df.show(
            truncate=False,
        )

        # -------------------------------------------------
        # Convert metrics to PostgreSQL metadata format
        # -------------------------------------------------

        dq_results_df = prepare_dq_results(
            metrics_df
        )

        print("=" * 70)
        print("DQ RESULTS TO PERSIST")
        print("=" * 70)

        dq_results_df.show(
            truncate=False,
        )

        # -------------------------------------------------
        # Persist results
        # -------------------------------------------------

        persist_dq_results(
            dq_results_df
        )

        # -------------------------------------------------
        # Overall Deequ status
        # -------------------------------------------------

        status = str(
            verification_result.status
        )

        print("=" * 70)
        print(
            f"Deequ verification status: {status}"
        )
        print("=" * 70)

        if status != "Success":
            raise ValueError(
                "Deequ Silver data-quality validation failed."
            )

        print(
            "Deequ Silver validation: PASSED"
        )

    finally:
        spark.stop()


if __name__ == "__main__":
    import os
    import sys
    import traceback

    exit_code = 0

    try:
        main()
    except BaseException:
        traceback.print_exc()
        exit_code = 1

    sys.stdout.flush()
    sys.stderr.flush()

    os._exit(exit_code)
