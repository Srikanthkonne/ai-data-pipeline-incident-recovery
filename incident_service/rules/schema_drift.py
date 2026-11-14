from typing import Any


DEFAULT_DATASET_NAME = "silver.transactions"


EXPECTED_SILVER_SCHEMA = {
    "transaction_id": "string",
    "customer_id": "string",
    "order_id": "string",
    "payment_id": "string",
    "amount": "double",
    "payment_method": "string",
    "status": "string",
    "event_time": "timestamp",
    "kafka_key": "string",
    "kafka_topic": "string",
    "kafka_partition": "int",
    "kafka_offset": "bigint",
    "kafka_timestamp": "timestamp",
    "ingestion_timestamp": "timestamp",
    "silver_processed_at": "timestamp",
}


def compare_schema(
    actual_schema: dict[str, str],
    expected_schema: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Compare an observed Silver schema with the expected contract.

    Detects:
      - MISSING_COLUMN
      - UNEXPECTED_COLUMN
      - TYPE_CHANGE
    """
    expected = expected_schema or EXPECTED_SILVER_SCHEMA

    detections: list[dict[str, Any]] = []

    expected_columns = set(expected)
    actual_columns = set(actual_schema)

    # Expected column disappeared.
    for column_name in sorted(
        expected_columns - actual_columns
    ):
        detections.append(
            {
                "drift_type": "MISSING_COLUMN",
                "column_name": column_name,
                "expected_type": expected[column_name],
                "actual_type": None,
            }
        )

    # New column appeared unexpectedly.
    for column_name in sorted(
        actual_columns - expected_columns
    ):
        detections.append(
            {
                "drift_type": "UNEXPECTED_COLUMN",
                "column_name": column_name,
                "expected_type": None,
                "actual_type": actual_schema[column_name],
            }
        )

    # Existing column changed type.
    for column_name in sorted(
        expected_columns & actual_columns
    ):
        expected_type = expected[column_name]
        actual_type = actual_schema[column_name]

        if actual_type != expected_type:
            detections.append(
                {
                    "drift_type": "TYPE_CHANGE",
                    "column_name": column_name,
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                }
            )

    return detections


def create_schema_drift_incident(
    evidence_path: str = (
        "spark/evidence/silver_schema.json"
    ),
) -> dict[str, Any]:
    """
    Detect schema drift from Spark-captured evidence and create
    one incident per unique schema snapshot.

    Re-running the detector against the same schema snapshot
    will not create a duplicate incident.
    """
    import json

    from metadata.repository.schema_snapshots import (
        record_schema_snapshot,
    )

    from incident_service.repository import (
        create_incident,
        get_incident_by_schema_snapshot,
    )

    with open(
        evidence_path,
        "r",
        encoding="utf-8",
    ) as file:
        evidence = json.load(file)

    observed_schema = evidence["schema"]

    detections = compare_schema(
        observed_schema
    )

    if not detections:
        return {
            "action": "no_drift",
            "incident": None,
            "detections": [],
        }

    snapshot = record_schema_snapshot(
        namespace=evidence["namespace"],
        name=evidence["name"],
        schema=observed_schema,
    )

    schema_snapshot_id = snapshot["id"]

    existing_incident = (
        get_incident_by_schema_snapshot(
            incident_type="SCHEMA_DRIFT",
            schema_snapshot_id=schema_snapshot_id,
        )
    )

    if existing_incident:
        return {
            "action": "skipped_existing",
            "incident": existing_incident,
            "detections": detections,
        }

    changed_columns = [
        detection["column_name"]
        for detection in detections
    ]

    incident = create_incident(
        incident_type="SCHEMA_DRIFT",
        dataset_name=DEFAULT_DATASET_NAME,
        source_system="spark",
        severity="HIGH",
        title=(
            "Schema drift detected in "
            f"{DEFAULT_DATASET_NAME}"
        ),
        description=(
            f"Detected {len(detections)} schema "
            f"change(s): "
            f"{', '.join(changed_columns)}."
        ),
        metadata={
            "lineage_entity_type": "Dataset",
            "lineage_namespace": evidence["namespace"],
            "lineage_name": evidence["name"],
            "schema_snapshot_id": schema_snapshot_id,
            "schema_hash": snapshot["schema_hash"],
            "namespace": evidence["namespace"],
            "dataset_name": evidence["name"],
            "source_path": evidence["source_path"],
            "captured_at": evidence["captured_at"],
            "detections": detections,
            "observed_schema": observed_schema,
        },
    )

    return {
        "action": "created",
        "incident": incident,
        "detections": detections,
    }
