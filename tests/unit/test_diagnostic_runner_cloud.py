from pathlib import Path

from incident_service.rca.diagnostics import runner


def test_runtime_provenance_survives_missing_bronze_evidence(
    monkeypatch,
    tmp_path,
):
    missing_bronze = (
        tmp_path / "bronze_schema.json"
    )

    monkeypatch.setattr(
        runner,
        "BRONZE_SCHEMA_EVIDENCE",
        missing_bronze,
    )

    monkeypatch.setattr(
        runner,
        "diagnose_runtime_provenance",
        lambda incident_id: {
            "diagnostic_type":
                "RUNTIME_PROVENANCE",
            "incident_id":
                incident_id,
            "runtime_execution_proven":
                True,
            "causal_evidence_eligible":
                True,
        },
    )

    result = (
        runner.collect_diagnostic_evidence(
            incident_id=9001,
            incident_type="SCHEMA_DRIFT",
        )
    )

    assert result[0][
        "diagnostic_type"
    ] == "RUNTIME_PROVENANCE"

    assert result[0][
        "causal_evidence_eligible"
    ] is True

    assert result[1] == {
        "diagnostic_type":
            "SCHEMA_COLUMN_ORIGIN",
        "status":
            "EVIDENCE_UNAVAILABLE",
        "reason":
            "Bronze schema evidence file "
            "was not available.",
    }
