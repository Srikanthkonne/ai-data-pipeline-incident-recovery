# import socket
# from datetime import datetime, timedelta

# from airflow import DAG
# from airflow.operators.python import PythonOperator


# DEFAULT_ARGS = {
#     "owner": "data-engineering",
#     "depends_on_past": False,
#     "retries": 2,
#     "retry_delay": timedelta(seconds=10),
# }


# def check_service(host: str, port: int, service_name: str) -> None:
#     """
#     Verify that a required pipeline service is reachable
#     from the Airflow network.
#     """

#     try:
#         with socket.create_connection(
#             (host, port),
#             timeout=5,
#         ):
#             print(
#                 f"{service_name} is reachable "
#                 f"at {host}:{port}"
#             )

#     except OSError as error:
#         raise RuntimeError(
#             f"{service_name} is not reachable "
#             f"at {host}:{port}"
#         ) from error


# def check_postgres() -> None:
#     check_service(
#         host="postgres",
#         port=5432,
#         service_name="Source PostgreSQL",
#     )


# def check_kafka() -> None:
#     check_service(
#         host="kafka",
#         port=29092,
#         service_name="Kafka",
#     )


# def check_minio() -> None:
#     check_service(
#         host="minio",
#         port=9000,
#         service_name="MinIO",
#     )


# with DAG(
#     dag_id="pipeline_infrastructure_health",
#     description=(
#         "Validate connectivity to core data "
#         "pipeline infrastructure services."
#     ),
#     default_args=DEFAULT_ARGS,
#     start_date=datetime(2026, 9, 1),
#     schedule=None,
#     catchup=False,
#     tags=[
#         "data-platform",
#         "health-check",
#         "phase-1",
#     ],
# ) as dag:

#     check_postgres_task = PythonOperator(
#         task_id="check_postgres",
#         python_callable=check_postgres,
#     )

#     check_kafka_task = PythonOperator(
#         task_id="check_kafka",
#         python_callable=check_kafka,
#     )

#     check_minio_task = PythonOperator(
#         task_id="check_minio",
#         python_callable=check_minio,
#     )

#     (
#         check_postgres_task
#         >> check_kafka_task
#         >> check_minio_task
#     )

import os
import socket
from datetime import datetime, timedelta

import boto3

from airflow import DAG
from airflow.operators.python import PythonOperator


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(seconds=10),
}


MINIO_ENDPOINT = "http://minio:9000"
MINIO_BUCKET = "data-platform"
BRONZE_PREFIX = "bronze/transactions/"


def check_service(
    host: str,
    port: int,
    service_name: str,
) -> None:
    try:
        with socket.create_connection(
            (host, port),
            timeout=5,
        ):
            print(
                f"{service_name} is reachable "
                f"at {host}:{port}"
            )

    except OSError as error:
        raise RuntimeError(
            f"{service_name} is not reachable "
            f"at {host}:{port}"
        ) from error


def check_postgres() -> None:
    check_service(
        host="postgres",
        port=5432,
        service_name="Source PostgreSQL",
    )


def check_kafka() -> None:
    check_service(
        host="kafka",
        port=29092,
        service_name="Kafka",
    )


def check_minio() -> None:
    check_service(
        host="minio",
        port=9000,
        service_name="MinIO",
    )


def get_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    )


def validate_bronze_dataset() -> None:
    s3_client = get_minio_client()

    response = s3_client.list_objects_v2(
        Bucket=MINIO_BUCKET,
        Prefix=BRONZE_PREFIX,
    )

    objects = response.get(
        "Contents",
        [],
    )

    parquet_files = [
        obj
        for obj in objects
        if obj["Key"].endswith(".parquet")
    ]

    if not parquet_files:
        raise RuntimeError(
            "No Bronze Parquet files found at "
            f"s3://{MINIO_BUCKET}/{BRONZE_PREFIX}"
        )

    print(
        f"Bronze validation successful: "
        f"{len(parquet_files)} Parquet file(s) found."
    )

    for parquet_file in parquet_files[:5]:
        print(
            f"Found: {parquet_file['Key']}"
        )


with DAG(
    dag_id="pipeline_infrastructure_health",
    description=(
        "Validate infrastructure connectivity "
        "and Bronze dataset availability."
    ),
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 9, 1),
    schedule=None,
    catchup=False,
    tags=[
        "data-platform",
        "health-check",
        "phase-1",
    ],
) as dag:

    check_postgres_task = PythonOperator(
        task_id="check_postgres",
        python_callable=check_postgres,
    )

    check_kafka_task = PythonOperator(
        task_id="check_kafka",
        python_callable=check_kafka,
    )

    check_minio_task = PythonOperator(
        task_id="check_minio",
        python_callable=check_minio,
    )

    validate_bronze_task = PythonOperator(
        task_id="validate_bronze_dataset",
        python_callable=validate_bronze_dataset,
    )

    (
        check_postgres_task
        >> check_kafka_task
        >> check_minio_task
        >> validate_bronze_task
    )