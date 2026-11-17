import os
from pathlib import Path
from uuid import uuid4

import pytest


pytestmark = pytest.mark.aws_integration

# Critical cost guard:
# normal pytest must never start real AWS resources.
if os.getenv("RUN_AWS_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "Real AWS integration tests are disabled. "
        "Set RUN_AWS_INTEGRATION_TESTS=1 explicitly.",
        allow_module_level=True,
    )


from incident_service.db import get_db_connection
from incident_service.rca.diagnostics.runtime_provenance import (
    diagnose_runtime_provenance,
)
from incident_service.recovery.adapters.base import (
    ExecutionStep,
)
from incident_service.recovery.adapters.config import (
    RecoveryExecutionConfig,
    RecoveryStorageConfig,
)
from incident_service.recovery.adapters.factory import (
    build_execution_adapter,
)
from incident_service.recovery.validator import (
    validate_schema_drift_recovery,
)
from incident_service.rules.schema_drift import (
    create_schema_drift_incident,
)
from metadata.repository.datasets import (
    sync_dataset_technical_metadata,
)


INJECTOR_HOST_PATH = Path(
    "failure_injection/scenarios/inject_schema_drift.py"
)

INJECTOR_RUNTIME_PATH = (
    "/opt/spark/work-dir/"
    "failure_injection/scenarios/"
    "inject_schema_drift.py"
)

LOCAL_PROVENANCE_DIR = Path(
    "spark/evidence/failure_injections"
)


def _split_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(
            f"Expected s3:// URI, received: {uri}"
        )

    remainder = uri[5:]
    bucket, separator, key = remainder.partition("/")

    if not bucket or not separator or not key:
        raise ValueError(
            f"Invalid S3 URI: {uri}"
        )

    return bucket, key.rstrip("/")


def _list_prefix_keys(
    s3_client,
    uri: str,
) -> list[str]:
    bucket, prefix = _split_s3_uri(uri)
    prefix = prefix.rstrip("/") + "/"

    keys: list[str] = []

    paginator = s3_client.get_paginator(
        "list_objects_v2"
    )

    for page in paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
    ):
        for item in page.get("Contents", []):
            keys.append(item["Key"])

    return keys


def _delete_prefix(
    s3_client,
    uri: str,
) -> None:
    bucket, _ = _split_s3_uri(uri)
    keys = _list_prefix_keys(
        s3_client,
        uri,
    )

    for offset in range(0, len(keys), 1000):
        batch = keys[offset:offset + 1000]

        if not batch:
            continue

        s3_client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [
                    {"Key": key}
                    for key in batch
                ],
                "Quiet": True,
            },
        )


def _replace_prefix_from_backup(
    s3_client,
    *,
    backup_uri: str,
    destination_uri: str,
) -> None:
    source_bucket, source_prefix = (
        _split_s3_uri(backup_uri)
    )
    destination_bucket, destination_prefix = (
        _split_s3_uri(destination_uri)
    )

    source_prefix = (
        source_prefix.rstrip("/") + "/"
    )
    destination_prefix = (
        destination_prefix.rstrip("/") + "/"
    )

    source_keys = _list_prefix_keys(
        s3_client,
        backup_uri,
    )

    # Never delete the live dataset unless the
    # known-good backup definitely exists.
    if not source_keys:
        raise AssertionError(
            "Schema-drift backup is empty; "
            "refusing to replace live Silver."
        )

    _delete_prefix(
        s3_client,
        destination_uri,
    )

    for source_key in source_keys:
        relative_key = source_key[
            len(source_prefix):
        ]

        if not relative_key:
            continue

        destination_key = (
            destination_prefix
            + relative_key
        )

        s3_client.copy_object(
            Bucket=destination_bucket,
            CopySource={
                "Bucket": source_bucket,
                "Key": source_key,
            },
            Key=destination_key,
        )


def _cleanup_incident(
    incident_id: int | None,
) -> None:
    if incident_id is None:
        return

    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM recovery_queue
                WHERE incident_id = %s;
                """,
                (incident_id,),
            )

            cursor.execute(
                """
                DELETE FROM recovery_attempts
                WHERE incident_id = %s;
                """,
                (incident_id,),
            )

            cursor.execute(
                """
                DELETE FROM incidents
                WHERE incident_id = %s;
                """,
                (incident_id,),
            )

        conn.commit()
    finally:
        conn.close()


def test_real_aws_schema_drift_boundary():
    """
    Opt-in real-cloud integration test.

    Covers:
      1. production execution/storage configuration
      2. S3 healthy-baseline restoration
      3. schema-drift injection on EMR Serverless
      4. provenance persisted to S3
      5. provenance fetched through the adapter
      6. cloud schema validation on EMR Serverless
      7. SCHEMA_DRIFT incident creation
      8. runtime-provenance causal correlation
      9. fail-safe restoration of healthy Silver

    This intentionally does not call Gemini or execute
    the full recovery orchestrator. Those layers are
    covered separately, while the real full-cloud path
    has already been manually validated.
    """

    execution_config = (
        RecoveryExecutionConfig.from_env()
    )
    storage_config = (
        RecoveryStorageConfig.from_env()
    )

    if (
        execution_config.backend
        != "emr-serverless"
    ):
        pytest.fail(
            "AWS integration test requires "
            "RECOVERY_EXECUTION_BACKEND="
            "emr-serverless."
        )

    if storage_config.backend != "aws-s3":
        pytest.fail(
            "AWS integration test requires "
            "RECOVERY_STORAGE_BACKEND=aws-s3."
        )

    adapter = build_execution_adapter(
        config=execution_config
    )

    assert adapter.name == "emr-serverless"

    if not INJECTOR_HOST_PATH.is_file():
        pytest.fail(
            "Schema-drift injector was not found: "
            f"{INJECTOR_HOST_PATH}"
        )

    execution_id = uuid4().hex

    drift_column = (
        "phase5b_aws_integration_"
        f"{execution_id[:12]}"
    )

    drift_value = "AWS_INTEGRATION_TEST"

    artifact_bucket = (
        execution_config
        .emr_serverless_artifact_bucket
    )

    artifact_prefix = (
        execution_config
        .emr_serverless_artifact_prefix
    )

    assert artifact_bucket is not None

    provenance_prefix = (
        f"s3://{artifact_bucket}/"
        f"{artifact_prefix}/"
        "evidence/failure_injections"
    )

    provenance_filename = (
        f"schema_drift_{execution_id}.json"
    )

    provenance_uri = (
        provenance_prefix.rstrip("/")
        + "/"
        + provenance_filename
    )

    local_provenance_path = (
        LOCAL_PROVENANCE_DIR
        / provenance_filename
    )

    LOCAL_PROVENANCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if local_provenance_path.exists():
        local_provenance_path.unlink()

    incident_id: int | None = None

    s3_client = adapter.s3_client

    # Force a known healthy starting point using the
    # immutable schema-drift backup. This uses S3 object
    # operations and does not start another EMR job.
    _replace_prefix_from_backup(
        s3_client,
        backup_uri=storage_config.backup_path,
        destination_uri=storage_config.silver_path,
    )

    try:
        environment = (
            storage_config.environment()
        )

        environment.update(
            {
                "SCHEMA_DRIFT_EXECUTION_ID":
                    execution_id,
                "SCHEMA_DRIFT_COLUMN":
                    drift_column,
                "SCHEMA_DRIFT_VALUE":
                    drift_value,
                "RECOVERY_PROVENANCE_URI_PREFIX":
                    provenance_prefix,
            }
        )

        stage_result = adapter.execute_step(
            ExecutionStep(
                operation="STAGE_FILE",
                parameters={
                    "source_path":
                        str(INJECTOR_HOST_PATH),
                    "destination_path":
                        INJECTOR_RUNTIME_PATH,
                },
            ),
            timeout_seconds=180,
        )

        assert stage_result.returncode == 0

        injection_result = adapter.execute_step(
            ExecutionStep(
                operation="RUN_SPARK_SCRIPT",
                parameters={
                    "script_path":
                        INJECTOR_RUNTIME_PATH,
                    "environment":
                        environment,
                },
            ),
            timeout_seconds=600,
        )

        assert injection_result.returncode == 0

        fetch_result = adapter.execute_step(
            ExecutionStep(
                operation="FETCH_FILE",
                parameters={
                    "source_path":
                        provenance_uri,
                    "destination_path":
                        str(
                            local_provenance_path
                        ),
                },
            ),
            timeout_seconds=180,
        )

        assert fetch_result.returncode == 0
        assert local_provenance_path.is_file()

        validation = (
            validate_schema_drift_recovery(
                execution_adapter=adapter,
                storage_config=storage_config,
            )
        )

        assert validation["healthy"] is False
        assert (
            validation["recovery_needed"]
            is True
        )
        assert (
            validation["execution_backend"]
            == "emr-serverless"
        )
        assert (
            validation["storage_backend"]
            == "aws-s3"
        )
        assert (
            validation["schema_column_count"]
            == 16
        )

        assert any(
            detection.get("drift_type")
            == "UNEXPECTED_COLUMN"
            and detection.get("column_name")
            == drift_column
            for detection
            in validation[
                "remaining_detections"
            ]
        )

        # Schema snapshots require the cloud dataset to
        # exist in the technical metadata registry.
        sync_dataset_technical_metadata(
            namespace=(
                storage_config.dataset_namespace
            ),
            name=storage_config.dataset_name,
            layer="silver",
        )

        detection_result = (
            create_schema_drift_incident()
        )

        assert (
            detection_result["action"]
            == "created"
        )

        incident = detection_result[
            "incident"
        ]

        assert incident is not None

        incident_id = incident[
            "incident_id"
        ]

        provenance = (
            diagnose_runtime_provenance(
                incident_id
            )
        )

        assert (
            provenance[
                "runtime_execution_proven"
            ]
            is True
        )
        assert (
            provenance[
                "causal_evidence_eligible"
            ]
            is True
        )
        assert (
            provenance["execution_id"]
            == execution_id
        )
        assert (
            provenance["injected_column"]
            == drift_column
        )
        assert (
            provenance["evidence_strength"]
            == "STRONG_RUNTIME_PROVENANCE"
        )

    finally:
        # Fail-safe: always put the healthy backup back
        # into the live Silver path, even when an
        # assertion or cloud operation above fails.
        _replace_prefix_from_backup(
            s3_client,
            backup_uri=storage_config.backup_path,
            destination_uri=storage_config.silver_path,
        )

        # Remove any leftover temporary Spark output.
        _delete_prefix(
            s3_client,
            storage_config.temp_path,
        )

        # Remove test-only provenance from S3.
        provenance_bucket, provenance_key = (
            _split_s3_uri(
                provenance_uri
            )
        )

        s3_client.delete_object(
            Bucket=provenance_bucket,
            Key=provenance_key,
        )

        if local_provenance_path.exists():
            local_provenance_path.unlink()

        _cleanup_incident(
            incident_id
        )
