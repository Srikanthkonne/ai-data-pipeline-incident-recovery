import json

from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from incident_service.recovery.adapters import (
    ExecutionAdapterError,
    ExecutionAdapterTimeoutError,
    ExecutionStep,
    RecoveryExecutionAdapter,
)
from incident_service.recovery.adapters.config import (
    RecoveryStorageConfig,
)
from incident_service.recovery.adapters.factory import (
    build_execution_adapter,
)
from incident_service.rules.schema_drift import (
    compare_schema,
)


CAPTURE_SCRIPT_HOST = Path(
    "spark/jobs/capture_silver_schema.py"
)

CAPTURE_SCRIPT_RUNTIME = (
    "/tmp/capture_silver_schema.py"
)

EVIDENCE_PATH = Path(
    "spark/evidence/silver_schema.json"
)


class RecoveryValidationError(RuntimeError):
    pass


def _validate_backend_pair(
    adapter: RecoveryExecutionAdapter,
    storage_config: RecoveryStorageConfig,
) -> None:
    if (
        adapter.name == "emr-serverless"
        and storage_config.backend != "aws-s3"
    ):
        raise RecoveryValidationError(
            "EMR Serverless validation requires "
            "RECOVERY_STORAGE_BACKEND=aws-s3."
        )

    if (
        adapter.name == "local-docker"
        and storage_config.backend != "minio"
    ):
        raise RecoveryValidationError(
            "Local Docker validation requires "
            "RECOVERY_STORAGE_BACKEND=minio."
        )


def validate_schema_drift_recovery(
    *,
    execution_adapter: Optional[
        RecoveryExecutionAdapter
    ] = None,
    storage_config: Optional[
        RecoveryStorageConfig
    ] = None,
) -> dict[str, Any]:
    """
    Capture the current Silver schema through the
    configured execution/storage backends and compare
    it with the expected schema contract.

    The same function is used before and after recovery.
    """

    adapter = (
        execution_adapter
        if execution_adapter is not None
        else build_execution_adapter()
    )

    storage = (
        storage_config
        if storage_config is not None
        else RecoveryStorageConfig.from_env()
    )

    _validate_backend_pair(
        adapter,
        storage,
    )

    if not CAPTURE_SCRIPT_HOST.is_file():
        raise RecoveryValidationError(
            "Schema capture script was not found: "
            f"{CAPTURE_SCRIPT_HOST}"
        )

    # Never allow an old local evidence file to satisfy
    # a failed or incomplete new validation attempt.
    if EVIDENCE_PATH.exists():
        EVIDENCE_PATH.unlink()

    evidence_source_path = (
        storage.schema_evidence_path
    )

    if storage.backend == "aws-s3":
        configured_path = (
            storage.schema_evidence_path
            .rstrip("/")
        )

        if configured_path.endswith(".json"):
            evidence_prefix = (
                configured_path.rsplit(
                    "/",
                    1,
                )[0]
            )
        else:
            evidence_prefix = configured_path

        evidence_source_path = (
            f"{evidence_prefix}/"
            f"silver_schema_{uuid4().hex}.json"
        )

    environment = storage.environment(
        evidence_path=evidence_source_path,
    )

    stage_step = ExecutionStep(
        operation="STAGE_FILE",
        parameters={
            "source_path":
                str(CAPTURE_SCRIPT_HOST),
            "destination_path":
                CAPTURE_SCRIPT_RUNTIME,
        },
    )

    capture_step = ExecutionStep(
        operation="RUN_SPARK_SCRIPT",
        parameters={
            "script_path":
                CAPTURE_SCRIPT_RUNTIME,
            "environment":
                environment,
        },
    )

    fetch_step = ExecutionStep(
        operation="FETCH_FILE",
        parameters={
            "source_path":
                evidence_source_path,
            "destination_path":
                str(EVIDENCE_PATH),
        },
    )

    try:
        adapter.execute_step(
            stage_step,
            timeout_seconds=180,
        )

        validation_timeout_seconds = (
            600
            if adapter.name == "emr-serverless"
            else 180
        )

        completed = adapter.execute_step(
            capture_step,
            timeout_seconds=validation_timeout_seconds,
        )

        adapter.execute_step(
            fetch_step,
            timeout_seconds=180,
        )

    except ExecutionAdapterTimeoutError as exc:
        raise RecoveryValidationError(
            "Schema validation execution timed out."
        ) from exc

    except ExecutionAdapterError as exc:
        raise RecoveryValidationError(
            "Schema validation execution failed."
        ) from exc

    if not EVIDENCE_PATH.exists():
        raise RecoveryValidationError(
            "Silver schema evidence file "
            f"not found: {EVIDENCE_PATH}"
        )

    try:
        evidence = json.loads(
            EVIDENCE_PATH.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise RecoveryValidationError(
            "Silver schema evidence could not "
            "be read."
        ) from exc

    dataset_exists = evidence.get(
        "dataset_exists"
    )

    capture_status = evidence.get(
        "capture_status"
    )

    observed_schema = evidence.get(
        "schema",
        {},
    )

    if (
        dataset_exists is False
        or capture_status == "MISSING_DATASET"
    ):
        return {
            "validation_type":
                "SCHEMA_DRIFT_RECOVERY",
            "healthy":
                False,
            "recovery_needed":
                True,
            "dataset_exists":
                False,
            "capture_status":
                "MISSING_DATASET",
            "schema_column_count":
                0,
            "remaining_detections": [
                {
                    "type":
                        "MISSING_DATASET",
                    "dataset":
                        "silver/transactions",
                }
            ],
            "captured_at":
                evidence.get(
                    "captured_at"
                ),
            "source_path":
                evidence.get(
                    "source_path"
                ),
            "validation_command_returncode":
                completed.returncode,
            "execution_backend":
                adapter.name,
            "storage_backend":
                storage.backend,
        }

    if capture_status != "CAPTURED":
        raise RecoveryValidationError(
            "Unexpected schema capture status: "
            f"{capture_status!r}"
        )

    detections = compare_schema(
        observed_schema
    )

    healthy = len(detections) == 0

    return {
        "validation_type":
            "SCHEMA_DRIFT_RECOVERY",
        "healthy":
            healthy,
        "recovery_needed":
            not healthy,
        "dataset_exists":
            True,
        "capture_status":
            capture_status,
        "schema_column_count":
            len(observed_schema),
        "remaining_detections":
            detections,
        "captured_at":
            evidence.get(
                "captured_at"
            ),
        "source_path":
            evidence.get(
                "source_path"
            ),
        "validation_command_returncode":
            completed.returncode,
        "execution_backend":
            adapter.name,
        "storage_backend":
            storage.backend,
    }
