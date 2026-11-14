import subprocess

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Optional


SPARK_CONTAINER = "incident-platform-spark"

RESTORE_SCRIPT_HOST = Path(
    "failure_injection/scenarios/"
    "restore_schema_drift.py"
)

RESTORE_SCRIPT_CONTAINER = (
    "/tmp/restore_schema_drift.py"
)

SPARK_SUBMIT = (
    "/opt/spark/bin/spark-submit"
)

SPARK_PACKAGES = (
    "org.apache.hadoop:hadoop-aws:3.3.4,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.262"
)

MAX_CAPTURED_LOG_CHARS = 4000
MAX_ERROR_LOG_CHARS = 2000


class RecoveryExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}


def _utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _normalize_output(
    value: Any,
) -> str:
    """
    Normalize subprocess output to safe text.
    """

    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(
            errors="replace"
        ).strip()

    return str(value).strip()


def _truncate_tail(
    value: Any,
    *,
    limit: int = MAX_CAPTURED_LOG_CHARS,
) -> dict[str, Any]:
    """
    Keep only the tail of command output while
    preserving truncation metadata.
    """

    text = _normalize_output(value)

    original_char_count = len(text)
    truncated = (
        original_char_count > limit
    )

    tail = (
        text[-limit:]
        if truncated
        else text
    )

    return {
        "tail": tail,
        "truncated": truncated,
        "original_char_count":
            original_char_count,
    }


def _schema_drift_restore_commands() -> list[list[str]]:
    return [
        [
            "docker",
            "cp",
            str(RESTORE_SCRIPT_HOST),
            (
                f"{SPARK_CONTAINER}:"
                f"{RESTORE_SCRIPT_CONTAINER}"
            ),
        ],
        [
            "docker",
            "exec",
            SPARK_CONTAINER,
            SPARK_SUBMIT,
            "--packages",
            SPARK_PACKAGES,
            "--conf",
            (
                "spark.driver.extraJavaOptions="
                "-Divy.cache.dir=/tmp/.ivy2"
            ),
            "--conf",
            "spark.jars.ivy=/tmp/.ivy2",
            RESTORE_SCRIPT_CONTAINER,
        ],
    ]


ACTION_REGISTRY = {
    "RESTORE_SCHEMA_DRIFT_BACKUP":
        _schema_drift_restore_commands,
}


def execute_recovery_action(
    decision: dict[str, Any],
    *,
    dry_run: bool = True,
    execution_guard: Optional[
        Callable[[], bool]
    ] = None,
) -> dict[str, Any]:
    """
    Execute only predefined allowlisted recovery
    actions.

    Persist bounded log tails rather than complete
    subprocess stdout/stderr.
    """

    action = decision.get("action")

    if not decision.get(
        "automatic_execution_allowed",
        False,
    ):
        raise RecoveryExecutionError(
            "Automatic execution is not allowed "
            "for this recovery decision."
        )

    command_factory = ACTION_REGISTRY.get(
        action
    )

    if command_factory is None:
        raise RecoveryExecutionError(
            "Recovery action is not allowlisted: "
            f"{action}"
        )

    if (
        action
        == "RESTORE_SCHEMA_DRIFT_BACKUP"
        and not RESTORE_SCRIPT_HOST.exists()
    ):
        raise RecoveryExecutionError(
            "Schema-drift restore script "
            f"not found: {RESTORE_SCRIPT_HOST}"
        )

    commands = command_factory()

    if dry_run:
        return {
            "action": action,
            "status": "DRY_RUN",
            "executed": False,
            "commands": commands,
            "log_capture_limit_chars":
                MAX_CAPTURED_LOG_CHARS,
        }

    execution_started_at = (
        _utc_now_iso()
    )
    execution_timer = perf_counter()

    results = []

    for command in commands:
        if execution_guard is not None:
            try:
                ownership_valid = (
                    execution_guard()
                )

            except Exception as exc:
                raise RecoveryExecutionError(
                    "Recovery execution guard failed.",
                    details={
                        "action": action,
                        "status": "FAILED",
                        "executed": bool(results),
                        "failure_type":
                            "EXECUTION_GUARD_ERROR",
                        "failed_command":
                            command,
                        "completed_steps":
                            results,
                    },
                ) from exc

            if not ownership_valid:
                raise RecoveryExecutionError(
                    "Recovery execution ownership lost.",
                    details={
                        "action": action,
                        "status": "FAILED",
                        "executed": bool(results),
                        "failure_type":
                            "EXECUTION_FENCE_REJECTED",
                        "failed_command":
                            command,
                        "completed_steps":
                            results,
                    },
                )

        step_started_at = (
            _utc_now_iso()
        )
        step_timer = perf_counter()

        try:
            completed = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                timeout=180,
            )

        except subprocess.TimeoutExpired as exc:
            stdout = _truncate_tail(
                exc.stdout,
                limit=MAX_ERROR_LOG_CHARS,
            )

            stderr = _truncate_tail(
                exc.stderr,
                limit=MAX_ERROR_LOG_CHARS,
            )

            failure_details = {
                "action": action,
                "status": "FAILED",
                "executed": True,
                "failure_type": "TIMEOUT",
                "failed_command": command,
                "timeout_seconds": 180,
                "completed_steps": results,
                "logs": {
                    "stdout_tail":
                        stdout["tail"],
                    "stderr_tail":
                        stderr["tail"],
                    "stdout_truncated":
                        stdout["truncated"],
                    "stderr_truncated":
                        stderr["truncated"],
                    "stdout_char_count":
                        stdout[
                            "original_char_count"
                        ],
                    "stderr_char_count":
                        stderr[
                            "original_char_count"
                        ],
                },
            }

            raise RecoveryExecutionError(
                "Recovery command timed out.",
                details=failure_details,
            ) from exc

        except subprocess.CalledProcessError as exc:
            stdout = _truncate_tail(
                exc.stdout,
                limit=MAX_ERROR_LOG_CHARS,
            )

            stderr = _truncate_tail(
                exc.stderr,
                limit=MAX_ERROR_LOG_CHARS,
            )

            failure_details = {
                "action": action,
                "status": "FAILED",
                "executed": True,
                "failure_type": "COMMAND_FAILED",
                "failed_command": command,
                "returncode": exc.returncode,
                "completed_steps": results,
                "logs": {
                    "stdout_tail":
                        stdout["tail"],
                    "stderr_tail":
                        stderr["tail"],
                    "stdout_truncated":
                        stdout["truncated"],
                    "stderr_truncated":
                        stderr["truncated"],
                    "stdout_char_count":
                        stdout[
                            "original_char_count"
                        ],
                    "stderr_char_count":
                        stderr[
                            "original_char_count"
                        ],
                },
            }

            raise RecoveryExecutionError(
                "Recovery command failed.",
                details=failure_details,
            ) from exc

        step_completed_at = (
            _utc_now_iso()
        )

        step_duration_ms = round(
            (
                perf_counter()
                - step_timer
            )
            * 1000,
            3,
        )

        stdout = _truncate_tail(
            completed.stdout
        )

        stderr = _truncate_tail(
            completed.stderr
        )

        results.append(
            {
                "command": command,
                "returncode":
                    completed.returncode,
                "started_at":
                    step_started_at,
                "completed_at":
                    step_completed_at,
                "duration_ms":
                    step_duration_ms,
                "logs": {
                    "stdout_tail":
                        stdout["tail"],
                    "stderr_tail":
                        stderr["tail"],
                    "stdout_truncated":
                        stdout["truncated"],
                    "stderr_truncated":
                        stderr["truncated"],
                    "stdout_char_count":
                        stdout[
                            "original_char_count"
                        ],
                    "stderr_char_count":
                        stderr[
                            "original_char_count"
                        ],
                },
            }
        )

    execution_completed_at = (
        _utc_now_iso()
    )

    execution_duration_ms = round(
        (
            perf_counter()
            - execution_timer
        )
        * 1000,
        3,
    )

    return {
        "action": action,
        "status": "COMPLETED",
        "executed": True,
        "started_at":
            execution_started_at,
        "completed_at":
            execution_completed_at,
        "duration_ms":
            execution_duration_ms,
        "log_capture_limit_chars":
            MAX_CAPTURED_LOG_CHARS,
        "steps":
            results,
    }
