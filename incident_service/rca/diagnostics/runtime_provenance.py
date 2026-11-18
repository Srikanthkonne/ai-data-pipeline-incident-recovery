import json

import boto3

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from incident_service.repository import (
    get_incident,
)


PROVENANCE_DIR = Path(
    "spark/evidence/failure_injections"
)

MAX_PROVENANCE_AGE_SECONDS = 15 * 60


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def _load_provenance_records(
    metadata: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """
    Load durable runtime provenance from S3 when
    runtime_provenance_uri is present in incident
    metadata.

    Existing local provenance files remain supported.
    """
    records: list[
        tuple[str, dict[str, Any]]
    ] = []

    provenance_uri = metadata.get(
        "runtime_provenance_uri"
    )

    if (
        isinstance(provenance_uri, str)
        and provenance_uri.startswith("s3://")
    ):
        parsed = urlparse(provenance_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        if bucket and key:
            try:
                response = boto3.client(
                    "s3"
                ).get_object(
                    Bucket=bucket,
                    Key=key,
                )

                record = json.loads(
                    response["Body"]
                    .read()
                    .decode("utf-8")
                )

            except (
                BotoCoreError,
                ClientError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ):
                pass

            else:
                records.append(
                    (
                        provenance_uri,
                        record,
                    )
                )

    for path in PROVENANCE_DIR.glob(
        "schema_drift_*.json"
    ):
        try:
            record = json.loads(
                path.read_text()
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        records.append(
            (
                str(path),
                record,
            )
        )

    return records


def diagnose_runtime_provenance(
    incident_id: int,
) -> dict[str, Any]:
    """
    Correlate a schema-drift incident with a completed
    controlled failure-injection runtime record.

    A match requires:
      - same scenario
      - same target dataset/path
      - same injected column
      - completed before schema capture
      - execution close to schema capture
      - injected column present in observed schema
      - resulting column count matches provenance
    """

    incident = get_incident(
        incident_id
    )

    if not incident:
        raise ValueError(
            f"Incident {incident_id} was not found."
        )

    if incident["incident_type"] != "SCHEMA_DRIFT":
        return {
            "diagnostic_type":
                "RUNTIME_PROVENANCE",
            "incident_id":
                incident_id,
            "runtime_execution_proven":
                False,
            "causal_evidence_eligible":
                False,
            "reason":
                "Incident is not SCHEMA_DRIFT.",
        }

    metadata = incident["metadata"]

    captured_at = _parse_timestamp(
        metadata["captured_at"]
    )

    observed_schema = metadata.get(
        "observed_schema",
        {},
    )

    drift_columns = {
        detection["column_name"]
        for detection in metadata.get(
            "detections",
            [],
        )
        if detection.get(
            "drift_type"
        ) == "UNEXPECTED_COLUMN"
    }

    matches = []

    for provenance_path, record in (
        _load_provenance_records(metadata)
    ):

        if record.get("scenario") != "SCHEMA_DRIFT":
            continue

        if record.get("status") != "COMPLETED":
            continue

        column = record.get(
            "injected_column"
        )

        if column not in drift_columns:
            continue

        if (
            record.get("target_dataset")
            != metadata.get("dataset_name")
        ):
            continue

        if (
            record.get("target_path")
            != metadata.get("source_path")
        ):
            continue

        completed_at_value = record.get(
            "completed_at"
        )

        if not completed_at_value:
            continue

        completed_at = _parse_timestamp(
            completed_at_value
        )

        age_seconds = (
            captured_at - completed_at
        ).total_seconds()

        if age_seconds < 0:
            continue

        if (
            age_seconds
            > MAX_PROVENANCE_AGE_SECONDS
        ):
            continue

        if column not in observed_schema:
            continue

        if (
            record.get("columns_after")
            != len(observed_schema)
        ):
            continue

        matches.append(
            {
                "path": provenance_path,
                "record": record,
                "age_seconds": age_seconds,
            }
        )

    if not matches:
        return {
            "diagnostic_type":
                "RUNTIME_PROVENANCE",
            "incident_id":
                incident_id,
            "runtime_execution_proven":
                False,
            "causal_evidence_eligible":
                False,
            "evidence_strength":
                "NONE",
            "conclusion":
                "NO_MATCHING_RUNTIME_PROVENANCE",
        }

    match = min(
        matches,
        key=lambda item:
            item["age_seconds"],
    )

    record = match["record"]

    return {
        "diagnostic_type":
            "RUNTIME_PROVENANCE",

        "incident_id":
            incident_id,

        "execution_id":
            record["execution_id"],

        "scenario":
            record["scenario"],

        "status":
            record["status"],

        "target_dataset":
            record["target_dataset"],

        "target_path":
            record["target_path"],

        "injected_column":
            record["injected_column"],

        "injected_value":
            record["injected_value"],

        "columns_before":
            record["columns_before"],

        "columns_after":
            record["columns_after"],

        "execution_started_at":
            record["started_at"],

        "execution_completed_at":
            record["completed_at"],

        "schema_captured_at":
            metadata["captured_at"],

        "seconds_before_schema_capture":
            match["age_seconds"],

        "provenance_file":
            match["path"],

        "runtime_execution_proven":
            True,

        "evidence_strength":
            "STRONG_RUNTIME_PROVENANCE",

        "causal_evidence_eligible":
            True,

        "conclusion":
            "CONTROLLED_SCHEMA_DRIFT_EXECUTION_"
            "MATCHES_INCIDENT",
    }
