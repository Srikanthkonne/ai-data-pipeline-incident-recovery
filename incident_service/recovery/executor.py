from incident_service.recovery.adapters import (
    ExecutionAdapterError,
    ExecutionAdapterTimeoutError,
    ExecutionStep,
    RecoveryExecutionAdapter,
)
from incident_service.recovery.adapters.factory import (
    build_execution_adapter,
)
from incident_service.recovery.adapters.config import (
    RecoveryStorageConfig,
)

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Optional


RESTORE_SCRIPT_HOST = Path(
    "failure_injection/scenarios/"
    "restore_schema_drift.py"
)

RESTORE_SCRIPT_CONTAINER = (
    "/tmp/restore_schema_drift.py"
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
    Normalize execution output to safe text.
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


def _schema_drift_restore_steps() -> list[ExecutionStep]:
    storage_config = RecoveryStorageConfig.from_env()

    return [
        ExecutionStep(
            operation="STAGE_FILE",
            parameters={
                "source_path": str(
                    RESTORE_SCRIPT_HOST
                ),
                "destination_path":
                    RESTORE_SCRIPT_CONTAINER,
            },
        ),
        ExecutionStep(
            operation="RUN_SPARK_SCRIPT",
            parameters={
                "script_path":
                    RESTORE_SCRIPT_CONTAINER,
                "environment":
                    storage_config.environment(),
            },
        ),
    ]


ACTION_REGISTRY = {
    "RESTORE_SCHEMA_DRIFT_BACKUP":
        _schema_drift_restore_steps,
}


def execute_recovery_action(
    decision: dict[str, Any],
    *,
    dry_run: bool = True,
    execution_guard: Optional[
        Callable[[], bool]
    ] = None,
    execution_adapter: Optional[
        RecoveryExecutionAdapter
    ] = None,
) -> dict[str, Any]:
    """
    Execute only predefined allowlisted recovery
    actions.

    Persist bounded log tails rather than complete
    execution stdout/stderr.
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

    step_factory = ACTION_REGISTRY.get(
        action
    )

    if step_factory is None:
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

    steps = step_factory()

    adapter = (
        execution_adapter
        if execution_adapter is not None
        else build_execution_adapter()
    )

    commands = [
        adapter.preview_step(step)
        for step in steps
    ]

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

    for step, command in zip(steps, commands):
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
            step_timeout_seconds = (
                600
                if (
                    adapter.name == "emr-serverless"
                    and step.operation == "RUN_SPARK_SCRIPT"
                )
                else 180
            )

            completed = adapter.execute_step(
                step,
                timeout_seconds=step_timeout_seconds,
            )

        except ExecutionAdapterTimeoutError as exc:
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
                "failed_command": (
                    exc.audit_descriptor
                    if exc.audit_descriptor is not None
                    else command
                ),
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

        except ExecutionAdapterError as exc:
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
                "failed_command": (
                    exc.audit_descriptor
                    if exc.audit_descriptor is not None
                    else command
                ),
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
                "command": (
                    completed.audit_descriptor
                    if completed.audit_descriptor is not None
                    else command
                ),
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
