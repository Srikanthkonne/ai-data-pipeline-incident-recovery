from typing import Any

from incident_service.repository import get_incident
from lineage.neo4j.queries import LineageQueryService


SUPPORTED_ENTITY_TYPES = {
    "Dataset",
    "Job",
}


def resolve_lineage_entity(
    incident: dict[str, Any],
) -> dict[str, str]:
    """
    Resolve the canonical Neo4j lineage identity stored
    in an incident's metadata.
    """
    metadata = incident.get("metadata") or {}

    entity_type = metadata.get(
        "lineage_entity_type"
    )
    namespace = metadata.get(
        "lineage_namespace"
    )
    name = metadata.get(
        "lineage_name"
    )

    if not entity_type:
        raise ValueError(
            "Incident metadata is missing "
            "lineage_entity_type."
        )

    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(
            f"Unsupported lineage entity type: "
            f"{entity_type}"
        )

    if not namespace or not name:
        raise ValueError(
            "Incident metadata is missing lineage "
            "namespace or name."
        )

    return {
        "node_type": entity_type,
        "namespace": namespace,
        "name": name,
    }


def investigate_incident(
    incident_id: int,
) -> dict[str, Any]:
    """
    Build deterministic lineage-based RCA evidence
    for an incident.

    Dataset incidents use Dataset lineage traversal.
    Job incidents use Job lineage traversal.
    """
    incident = get_incident(incident_id)

    if incident is None:
        raise ValueError(
            f"Incident {incident_id} does not exist."
        )

    entity = resolve_lineage_entity(
        incident
    )

    namespace = entity["namespace"]
    name = entity["name"]
    node_type = entity["node_type"]

    lineage = LineageQueryService()

    try:
        if node_type == "Dataset":
            upstream = lineage.get_upstream(
                namespace=namespace,
                name=name,
            )

            downstream = lineage.get_downstream(
                namespace=namespace,
                name=name,
            )

            blast_radius = (
                lineage.calculate_blast_radius(
                    namespace=namespace,
                    name=name,
                )
            )

        else:
            upstream = lineage.get_job_upstream(
                namespace=namespace,
                name=name,
            )

            downstream = lineage.get_job_downstream(
                namespace=namespace,
                name=name,
            )

            blast_radius = (
                lineage.calculate_job_blast_radius(
                    namespace=namespace,
                    name=name,
                )
            )

    finally:
        lineage.close()

    return {
        "incident_id": incident["incident_id"],
        "incident_type": incident["incident_type"],
        "severity": incident["severity"],
        "status": incident["status"],
        "lineage_entity": entity,
        "upstream": upstream,
        "downstream": downstream,
        "blast_radius": blast_radius,
    }
