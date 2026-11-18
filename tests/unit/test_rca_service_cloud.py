from incident_service.rca import service


def test_rca_degrades_when_neo4j_is_not_configured(
    monkeypatch,
):
    incident = {
        "incident_id": 1,
        "incident_type": "SCHEMA_DRIFT",
        "severity": "HIGH",
        "status": "OPEN",
        "metadata": {
            "lineage_entity_type": "Dataset",
            "lineage_namespace": (
                "s3://example-bucket"
            ),
            "lineage_name": "silver/transactions",
        },
    }

    monkeypatch.setattr(
        service,
        "get_incident",
        lambda incident_id: incident,
    )

    class MissingNeo4j:
        def __init__(self):
            raise RuntimeError(
                "NEO4J_PASSWORD is not set. "
                "Load the project .env before "
                "using lineage queries."
            )

    monkeypatch.setattr(
        service,
        "LineageQueryService",
        MissingNeo4j,
    )

    result = service.investigate_incident(1)

    assert result["incident_id"] == 1
    assert result["upstream"] == []
    assert result["downstream"] == []

    assert result["blast_radius"] == {
        "source": {
            "node_type": "Dataset",
            "namespace": "s3://example-bucket",
            "name": "silver/transactions",
        },
        "affected_datasets": [],
        "affected_dataset_count": 0,
        "affected_jobs": [],
        "affected_job_count": 0,
        "total_affected_nodes": 0,
        "max_hops": 0,
    }


def test_unexpected_lineage_runtime_error_is_not_hidden(
    monkeypatch,
):
    incident = {
        "incident_id": 1,
        "incident_type": "SCHEMA_DRIFT",
        "severity": "HIGH",
        "status": "OPEN",
        "metadata": {
            "lineage_entity_type": "Dataset",
            "lineage_namespace": "s3://example-bucket",
            "lineage_name": "silver/transactions",
        },
    }

    monkeypatch.setattr(
        service,
        "get_incident",
        lambda incident_id: incident,
    )

    class BrokenNeo4j:
        def __init__(self):
            raise RuntimeError(
                "Unexpected Neo4j initialization failure."
            )

    monkeypatch.setattr(
        service,
        "LineageQueryService",
        BrokenNeo4j,
    )

    try:
        service.investigate_incident(1)

    except RuntimeError as exc:
        assert (
            "Unexpected Neo4j initialization failure."
            in str(exc)
        )

    else:
        raise AssertionError(
            "Unexpected Neo4j errors must not be hidden."
        )
