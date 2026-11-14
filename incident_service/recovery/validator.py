import json
import subprocess

from pathlib import Path
from typing import Any

from incident_service.rules.schema_drift import (
    compare_schema,
)


SPARK_CONTAINER = "incident-platform-spark"

CAPTURE_SCRIPT = (
    "/opt/spark/work-dir/jobs/"
    "capture_silver_schema.py"
)

EVIDENCE_PATH = Path(
    "spark/evidence/silver_schema.json"
)

SPARK_PACKAGES = (
    "org.apache.hadoop:hadoop-aws:3.3.4,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.262"
)


class RecoveryValidationError(RuntimeError):
    pass


def validate_schema_drift_recovery(
) -> dict[str, Any]:
    """
    Capture the current Silver dataset state and
    determine whether schema recovery is needed.

    This function is safe to use both before and
    after recovery execution.

    Capture infrastructure failures raise
    RecoveryValidationError instead of being
    interpreted as a recoverable schema problem.
    """

    command = [
        "docker",
        "exec",
        SPARK_CONTAINER,
        "/opt/spark/bin/spark-submit",
        "--packages",
        SPARK_PACKAGES,
        "--conf",
        (
            "spark.driver.extraJavaOptions="
            "-Divy.cache.dir=/tmp/.ivy2"
        ),
        "--conf",
        "spark.jars.ivy=/tmp/.ivy2",
        CAPTURE_SCRIPT,
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=180,
        )

    except subprocess.TimeoutExpired as exc:
        raise RecoveryValidationError(
            "Schema validation timed out."
        ) from exc

    except subprocess.CalledProcessError as exc:
        raise RecoveryValidationError(
            "Schema validation command failed."
        ) from exc

    if not EVIDENCE_PATH.exists():
        raise RecoveryValidationError(
            "Silver schema evidence file "
            f"not found: {EVIDENCE_PATH}"
        )

    evidence = json.loads(
        EVIDENCE_PATH.read_text()
    )

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
        }

    if capture_status != "CAPTURED":
        raise RecoveryValidationError(
            "Unexpected schema capture status: "
            f"{capture_status!r}"
        )

    detections = compare_schema(
        observed_schema
    )

    healthy = (
        len(detections) == 0
    )

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
    }
