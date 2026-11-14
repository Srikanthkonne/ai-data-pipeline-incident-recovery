import os
from typing import Any

from psycopg2.extras import RealDictCursor

from incident_service.db import get_db_connection


DEFAULT_DATASET_NAME = "silver.transactions"
DEFAULT_NULL_RATE_THRESHOLD = float(
    os.getenv("NULL_SPIKE_THRESHOLD", "0.05")
)


def get_latest_completeness_results(
    dataset_name: str = DEFAULT_DATASET_NAME,
) -> list[dict[str, Any]]:
    """
    Return Completeness metrics from the latest Deequ run
    for the requested dataset.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT MAX(run_timestamp) AS latest_run_timestamp
                FROM data_quality_results
                WHERE dataset_name = %s;
                """,
                (dataset_name,),
            )

            latest = cursor.fetchone()

            if (
                latest is None
                or latest["latest_run_timestamp"] is None
            ):
                return []

            latest_run_timestamp = latest["latest_run_timestamp"]

            cursor.execute(
                """
                SELECT
                    id,
                    dataset_name,
                    check_name,
                    metric_name,
                    metric_value,
                    status,
                    details,
                    run_timestamp
                FROM data_quality_results
                WHERE dataset_name = %s
                  AND run_timestamp = %s
                  AND metric_name = 'Completeness'
                ORDER BY id;
                """,
                (
                    dataset_name,
                    latest_run_timestamp,
                ),
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    finally:
        conn.close()


def detect_null_spikes(
    dataset_name: str = DEFAULT_DATASET_NAME,
    threshold: float = DEFAULT_NULL_RATE_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Evaluate latest Deequ Completeness metrics.

    A null spike is detected when:

        null_rate > threshold

    where:

        null_rate = 1 - completeness
    """
    results = get_latest_completeness_results(dataset_name)

    detections = []

    for result in results:
        completeness = result["metric_value"]

        if completeness is None:
            continue

        null_rate = max(0.0, 1.0 - float(completeness))

        if null_rate > threshold:
            detections.append(
                {
                    "dq_result_id": result["id"],
                    "dataset_name": result["dataset_name"],
                    "column_name": result["check_name"],
                    "completeness": float(completeness),
                    "null_rate": null_rate,
                    "threshold": threshold,
                    "run_timestamp": result["run_timestamp"],
                }
            )

    return detections


def create_null_spike_incidents(
    dataset_name: str = DEFAULT_DATASET_NAME,
    threshold: float = DEFAULT_NULL_RATE_THRESHOLD,
    lineage_namespace: str = "s3://data-platform",
    lineage_name: str = "silver/transactions",
) -> list[dict[str, Any]]:
    """
    Detect null spikes and persist one incident per DQ evidence record.

    Re-running this function against the same DQ result will not
    create duplicate incidents.
    """
    from incident_service.repository import (
        create_incident,
        get_incident_by_dq_result,
    )

    detections = detect_null_spikes(
        dataset_name=dataset_name,
        threshold=threshold,
    )

    results = []

    for detection in detections:
        dq_result_id = detection["dq_result_id"]

        existing_incident = get_incident_by_dq_result(
            incident_type="NULL_SPIKE",
            dq_result_id=dq_result_id,
        )

        if existing_incident:
            results.append(
                {
                    "action": "skipped_existing",
                    "incident": existing_incident,
                }
            )
            continue

        column_name = detection["column_name"]
        null_rate = detection["null_rate"]

        incident = create_incident(
            incident_type="NULL_SPIKE",
            dataset_name=detection["dataset_name"],
            source_system="deequ",
            severity="HIGH",
            title=(
                f"Null spike detected in {column_name}"
            ),
            description=(
                f"Null rate for {column_name} reached "
                f"{null_rate:.2%}, exceeding the configured "
                f"threshold of {threshold:.2%}."
            ),
            metadata={
                "lineage_entity_type": "Dataset",
                "lineage_namespace": lineage_namespace,
                "lineage_name": lineage_name,
                "dq_result_id": dq_result_id,
                "column_name": column_name,
                "completeness": detection["completeness"],
                "null_rate": null_rate,
                "threshold": threshold,
                "dq_run_timestamp": (
                    detection["run_timestamp"].isoformat()
                ),
            },
        )

        results.append(
            {
                "action": "created",
                "incident": incident,
            }
        )

    return results
