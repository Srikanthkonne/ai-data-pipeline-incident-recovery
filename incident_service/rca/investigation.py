from datetime import date, datetime
from typing import Any

from incident_service.repository import get_incident
from incident_service.rca.service import investigate_incident
from metadata.repository.data_quality import (
    get_dq_result_by_id,
)
from metadata.repository.pipeline_runs import (
    get_pipeline_run_by_id,
)
from metadata.repository.schema_snapshots import (
    get_schema_snapshot_by_id,
)


def _make_json_safe(value: Any) -> Any:
    """
    Recursively convert values such as datetime objects
    into JSON-safe representations.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: _make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _make_json_safe(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _make_json_safe(item)
            for item in value
        ]

    return value


def collect_detector_evidence(
    incident: dict[str, Any],
) -> dict[str, Any]:
    """
    Retrieve the immutable detector evidence associated
    with an incident.
    """
    incident_type = incident["incident_type"]
    metadata = incident.get("metadata") or {}

    if incident_type == "NULL_SPIKE":
        evidence_id = metadata.get(
            "dq_result_id"
        )

        if evidence_id is None:
            raise ValueError(
                "NULL_SPIKE incident is missing "
                "dq_result_id."
            )

        evidence = get_dq_result_by_id(
            int(evidence_id)
        )

        evidence_type = "data_quality_result"

    elif incident_type == "SCHEMA_DRIFT":
        evidence_id = metadata.get(
            "schema_snapshot_id"
        )

        if evidence_id is None:
            raise ValueError(
                "SCHEMA_DRIFT incident is missing "
                "schema_snapshot_id."
            )

        evidence = get_schema_snapshot_by_id(
            int(evidence_id)
        )

        evidence_type = "schema_snapshot"

    elif incident_type == "SLA_BREACH":
        evidence_id = metadata.get(
            "pipeline_run_id"
        )

        if evidence_id is None:
            raise ValueError(
                "SLA_BREACH incident is missing "
                "pipeline_run_id."
            )

        evidence = get_pipeline_run_by_id(
            int(evidence_id)
        )

        evidence_type = "pipeline_run"

    else:
        raise ValueError(
            f"Unsupported incident type for RCA: "
            f"{incident_type}"
        )

    if evidence is None:
        raise ValueError(
            f"Evidence record {evidence_id} "
            f"was not found for incident "
            f"{incident['incident_id']}."
        )

    return {
        "evidence_type": evidence_type,
        "evidence_id": evidence_id,
        "record": evidence,
    }


def build_investigation_context(
    incident_id: int,
) -> dict[str, Any]:
    """
    Build the complete deterministic investigation
    context for an incident.

    This combines:
      - incident information
      - original detector evidence
      - upstream lineage
      - downstream lineage
      - blast radius
    """
    incident = get_incident(
        incident_id
    )

    if incident is None:
        raise ValueError(
            f"Incident {incident_id} does not exist."
        )

    detector_evidence = (
        collect_detector_evidence(
            incident
        )
    )

    lineage_evidence = (
        investigate_incident(
            incident_id
        )
    )

    context = {
        "incident": {
            "incident_id": incident[
                "incident_id"
            ],
            "incident_type": incident[
                "incident_type"
            ],
            "dataset_name": incident[
                "dataset_name"
            ],
            "source_system": incident[
                "source_system"
            ],
            "severity": incident[
                "severity"
            ],
            "status": incident[
                "status"
            ],
            "title": incident[
                "title"
            ],
            "description": incident[
                "description"
            ],
            "detected_at": incident[
                "detected_at"
            ],
            "resolved_at": incident[
                "resolved_at"
            ],
            "metadata": incident.get(
                "metadata"
            ) or {},
        },
        "detector_evidence": detector_evidence,
        "lineage": {
            "entity": lineage_evidence[
                "lineage_entity"
            ],
            "upstream": lineage_evidence[
                "upstream"
            ],
            "downstream": lineage_evidence[
                "downstream"
            ],
            "blast_radius": lineage_evidence[
                "blast_radius"
            ],
        },
    }

    return _make_json_safe(
        context
    )
