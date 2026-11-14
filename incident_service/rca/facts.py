from typing import Any

from incident_service.rca.investigation import (
    build_investigation_context,
)


def build_rca_facts(
    incident_id: int,
) -> dict[str, Any]:
    """
    Convert the full investigation context into a compact,
    deterministic fact package suitable for RCA reasoning.
    """
    context = build_investigation_context(
        incident_id
    )

    incident = context["incident"]
    evidence = context["detector_evidence"]
    lineage = context["lineage"]

    incident_type = incident["incident_type"]
    record = evidence["record"]

    if incident_type == "NULL_SPIKE":
        primary_signal = {
            "signal_type": "NULL_RATE",
            "column": incident["metadata"]["column_name"],
            "completeness": record["metric_value"],
            "null_rate": incident["metadata"]["null_rate"],
            "threshold": incident["metadata"]["threshold"],
            "dq_status": record["status"],
        }

    elif incident_type == "SCHEMA_DRIFT":
        primary_signal = {
            "signal_type": "SCHEMA_CHANGE",
            "detections": incident["metadata"]["detections"],
            "schema_snapshot_id": evidence["evidence_id"],
            "schema_hash": record["schema_hash"],
        }

    elif incident_type == "SLA_BREACH":
        primary_signal = {
            "signal_type": "EXECUTION_LATENCY",
            "run_id": record["run_id"],
            "duration_ms": record["duration_ms"],
            "sla_minutes": record["sla_minutes"],
            "run_status": record["status"],
        }

    else:
        raise ValueError(
            f"Unsupported incident type: {incident_type}"
        )

    return {
        "incident_id": incident["incident_id"],
        "incident_type": incident_type,
        "severity": incident["severity"],
        "status": incident["status"],
        "affected_entity": lineage["entity"],
        "primary_signal": primary_signal,
        "upstream_dependencies": lineage["upstream"],
        "downstream_dependencies": lineage["downstream"],
        "blast_radius": lineage["blast_radius"],
        "causal_evidence": [],
        "evidence_reference": {
            "evidence_type": evidence["evidence_type"],
            "evidence_id": evidence["evidence_id"],
        },
    }
