import json

from incident_service.recovery.adapters.base import (
    ExecutionStepResult,
)
from incident_service.recovery.adapters.config import (
    RecoveryStorageConfig,
)
from incident_service.rules.schema_drift import (
    EXPECTED_SILVER_SCHEMA,
)
from incident_service.recovery import validator


def test_validator_stage_run_fetch_flow(
    tmp_path,
    monkeypatch,
):
    evidence_path = (
        tmp_path / "silver_schema.json"
    )

    monkeypatch.setattr(
        validator,
        "EVIDENCE_PATH",
        evidence_path,
    )

    class FakeAdapter:
        name = "fake"

        def __init__(self):
            self.steps = []

        def execute_step(
            self,
            step,
            *,
            timeout_seconds,
        ):
            self.steps.append(step)

            if step.operation == "FETCH_FILE":
                destination = step.parameters[
                    "destination_path"
                ]

                with open(
                    destination,
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        {
                            "namespace":
                                "s3://data-platform",
                            "name":
                                "silver/transactions",
                            "source_path":
                                (
                                    "s3a://data-platform/"
                                    "silver/transactions"
                                ),
                            "captured_at":
                                "2026-11-16T00:00:00"
                                "+00:00",
                            "dataset_exists":
                                True,
                            "capture_status":
                                "CAPTURED",
                            "schema":
                                EXPECTED_SILVER_SCHEMA,
                        },
                        file,
                    )

            return ExecutionStepResult(
                audit_descriptor={
                    "operation":
                        step.operation,
                },
                returncode=0,
            )

    storage = RecoveryStorageConfig(
        backend="minio",
    )

    adapter = FakeAdapter()

    result = (
        validator
        .validate_schema_drift_recovery(
            execution_adapter=adapter,
            storage_config=storage,
        )
    )

    assert [
        step.operation
        for step in adapter.steps
    ] == [
        "STAGE_FILE",
        "RUN_SPARK_SCRIPT",
        "FETCH_FILE",
    ]

    run_step = adapter.steps[1]

    assert (
        run_step.parameters[
            "environment"
        ]["RECOVERY_STORAGE_BACKEND"]
        == "minio"
    )

    assert result["healthy"] is True
    assert result["recovery_needed"] is False
    assert result["schema_column_count"] == len(
        EXPECTED_SILVER_SCHEMA
    )
