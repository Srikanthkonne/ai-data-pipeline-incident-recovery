import json
from datetime import datetime
from pathlib import Path
from typing import Any

from incident_service.repository import (
    get_incident,
)
from metadata.repository.schema_snapshots import (
    get_schema_snapshot_by_id,
)


DEFAULT_BRONZE_EVIDENCE_PATH = Path(
    "spark/evidence/bronze_schema.json"
)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def diagnose_schema_column_origin(
    incident_id: int,
    bronze_evidence_path: Path = DEFAULT_BRONZE_EVIDENCE_PATH,
) -> dict[str, Any]:

    incident = get_incident(incident_id)

    if not incident:
        raise ValueError(
            f"Incident {incident_id} was not found."
        )

    if incident["incident_type"] != "SCHEMA_DRIFT":
        raise ValueError(
            "Schema-origin diagnostic requires "
            "a SCHEMA_DRIFT incident."
        )

    metadata = incident["metadata"]

    detections = metadata.get(
        "detections",
        [],
    )

    unexpected_columns = [
        item
        for item in detections
        if item.get("drift_type")
        == "UNEXPECTED_COLUMN"
    ]

    if not unexpected_columns:
        raise ValueError(
            "No unexpected-column drift found."
        )

    schema_snapshot_id = metadata[
        "schema_snapshot_id"
    ]

    silver_snapshot = (
        get_schema_snapshot_by_id(
            schema_snapshot_id
        )
    )

    if not silver_snapshot:
        raise ValueError(
            f"Schema snapshot {schema_snapshot_id} "
            "was not found."
        )

    bronze_evidence = json.loads(
        bronze_evidence_path.read_text()
    )

    bronze_schema = bronze_evidence[
        "schema"
    ]

    silver_schema = silver_snapshot[
        "schema_json"
    ]

    incident_time = _parse_timestamp(
        metadata["captured_at"]
    )

    bronze_time = _parse_timestamp(
        bronze_evidence["captured_at"]
    )

    diagnostics = []

    for detection in unexpected_columns:

        column = detection[
            "column_name"
        ]

        affected_present = (
            column in silver_schema
        )

        upstream_present = (
            column in bronze_schema
        )

        temporal_alignment = (
            bronze_time <= incident_time
        )

        if (
            affected_present
            and not upstream_present
        ):
            conclusion = (
                "COLUMN_PRESENT_IN_AFFECTED_"
                "ABSENT_IN_CURRENT_UPSTREAM"
            )
        else:
            conclusion = (
                "COLUMN_ORIGIN_NOT_NARROWED"
            )

        causal_evidence_eligible = (
            affected_present
            and not upstream_present
            and temporal_alignment
        )

        evidence_strength = (
            "STRONG"
            if causal_evidence_eligible
            else "SUPPORTING_NOT_CONCLUSIVE"
        )

        diagnostics.append(
            {
                "diagnostic_type":
                    "SCHEMA_COLUMN_ORIGIN",
                "column":
                    column,
                "affected_dataset":
                    metadata["dataset_name"],
                "affected_column_present":
                    affected_present,
                "upstream_dataset":
                    bronze_evidence["name"],
                "upstream_column_present":
                    upstream_present,
                "incident_captured_at":
                    metadata["captured_at"],
                "upstream_captured_at":
                    bronze_evidence["captured_at"],
                "temporal_alignment":
                    temporal_alignment,
                "evidence_strength":
                    evidence_strength,
                "causal_evidence_eligible":
                    causal_evidence_eligible,
                "conclusion":
                    conclusion,
            }
        )

    return {
        "incident_id":
            incident_id,
        "schema_snapshot_id":
            schema_snapshot_id,
        "diagnostics":
            diagnostics,
    }
