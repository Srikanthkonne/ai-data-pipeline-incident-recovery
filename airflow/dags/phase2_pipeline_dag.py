import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=15),
}


REQUIRED_CONTAINERS = [
    "incident-platform-spark",
    "incident-platform-minio",
    "incident-platform-marquez-api",
    "incident-platform-neo4j",
    "incident-postgres",
    "incident-platform-pipeline-runner",
]


def validate_phase2_runtime() -> None:
    """
    Fail fast if a required Phase 2 runtime container is not running.
    """
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--format",
            "{{.Names}}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    running_containers = set(
        result.stdout.splitlines()
    )

    missing = [
        container
        for container in REQUIRED_CONTAINERS
        if container not in running_containers
    ]

    if missing:
        raise RuntimeError(
            "Required Phase 2 container(s) are not running: "
            + ", ".join(missing)
        )

    print("Phase 2 runtime validation successful.")

    for container in REQUIRED_CONTAINERS:
        print(f"Running: {container}")


with DAG(
    dag_id="phase2_data_pipeline",
    description=(
        "Orchestrate Silver transformation, data quality, "
        "Gold dbt models, lineage graph sync, and metadata persistence."
    ),
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 9, 1),
    schedule=None,
    catchup=False,
    tags=[
        "data-platform",
        "phase-2",
        "lineage",
        "data-quality",
    ],
) as dag:

    validate_runtime_task = PythonOperator(
        task_id="validate_phase2_runtime",
        python_callable=validate_phase2_runtime,
    )

    run_silver_task = BashOperator(
        task_id="run_silver_transactions",
        bash_command=(
            "bash /opt/airflow/project/scripts/"
            "run_silver_transactions.sh;"
        ),
    )

    run_deequ_task = BashOperator(
        task_id="run_deequ_quality",
        bash_command=(
            "bash /opt/airflow/project/scripts/"
            "run_deequ_silver_quality.sh;"
        ),
    )

    run_dbt_task = BashOperator(
        task_id="run_dbt_build",
        bash_command="""
        docker exec incident-platform-pipeline-runner \
          bash -lc '
            cd /workspace/dbt/data_reliability_dbt &&
            dbt build --profiles-dir .
          '
        """,
    )

    sync_neo4j_task = BashOperator(
        task_id="sync_marquez_to_neo4j",
        bash_command="""
        docker exec incident-platform-pipeline-runner \
          python lineage/neo4j/sync_marquez_to_neo4j.py
        """,
    )

    sync_metadata_task = BashOperator(
        task_id="sync_marquez_metadata",
        bash_command="""
        docker exec incident-platform-pipeline-runner \
          python -m metadata.sync_marquez_metadata
        """,
    )

    (
        validate_runtime_task
        >> run_silver_task
        >> run_deequ_task
        >> run_dbt_task
        >> sync_neo4j_task
        >> sync_metadata_task
    )
