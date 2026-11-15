import pytest

from incident_service.recovery.adapters import (
    ExecutionAdapterError,
    ExecutionAdapterTimeoutError,
    ExecutionStep,
    ExecutionStepResult,
)
from incident_service.recovery.adapters.local_docker import (
    LocalDockerExecutionAdapter,
)
from incident_service.recovery.executor import (
    RecoveryExecutionError,
    execute_recovery_action,
)


DECISION = {
    "action": "RESTORE_SCHEMA_DRIFT_BACKUP",
    "automatic_execution_allowed": True,
}


def test_local_docker_adapter_builds_stage_file_command():
    adapter = LocalDockerExecutionAdapter()

    step = ExecutionStep(
        operation="STAGE_FILE",
        parameters={
            "source_path": "source.py",
            "destination_path": "/tmp/source.py",
        },
    )

    assert adapter.preview_step(step) == [
        "docker",
        "cp",
        "source.py",
        "incident-platform-spark:/tmp/source.py",
    ]


def test_local_docker_adapter_builds_spark_command():
    adapter = LocalDockerExecutionAdapter()

    step = ExecutionStep(
        operation="RUN_SPARK_SCRIPT",
        parameters={
            "script_path": "/tmp/job.py",
        },
    )

    command = adapter.preview_step(step)

    assert command[0:4] == [
        "docker",
        "exec",
        "incident-platform-spark",
        "/opt/spark/bin/spark-submit",
    ]
    assert command[-1] == "/tmp/job.py"


def test_execution_uses_actual_adapter_audit_descriptor():
    class FakeAdapter:
        name = "fake"

        def preview_step(self, step):
            return ["preview", step.operation]

        def execute_step(
            self,
            step,
            *,
            timeout_seconds,
        ):
            return ExecutionStepResult(
                audit_descriptor={
                    "provider": "fake-cloud",
                    "operation": step.operation,
                },
                returncode=0,
                stdout="ok",
                stderr="",
            )

    result = execute_recovery_action(
        DECISION,
        dry_run=False,
        execution_adapter=FakeAdapter(),
    )

    assert result["status"] == "COMPLETED"
    assert result["steps"][0]["command"] == {
        "provider": "fake-cloud",
        "operation": "STAGE_FILE",
    }


def test_execution_fence_blocks_second_step():
    class FakeAdapter:
        name = "fake"

        def __init__(self):
            self.executed = []

        def preview_step(self, step):
            return ["fake", step.operation]

        def execute_step(
            self,
            step,
            *,
            timeout_seconds,
        ):
            self.executed.append(step.operation)
            return ExecutionStepResult(
                audit_descriptor=[
                    "fake",
                    step.operation,
                ],
                returncode=0,
            )

    adapter = FakeAdapter()
    guard_calls = 0

    def execution_guard():
        nonlocal guard_calls
        guard_calls += 1
        return guard_calls == 1

    with pytest.raises(
        RecoveryExecutionError
    ) as exc_info:
        execute_recovery_action(
            DECISION,
            dry_run=False,
            execution_guard=execution_guard,
            execution_adapter=adapter,
        )

    assert adapter.executed == ["STAGE_FILE"]
    assert (
        exc_info.value.details["failure_type"]
        == "EXECUTION_FENCE_REJECTED"
    )


def test_timeout_error_preserves_existing_contract():
    class TimeoutAdapter:
        name = "timeout"

        def preview_step(self, step):
            return ["fake", step.operation]

        def execute_step(
            self,
            step,
            *,
            timeout_seconds,
        ):
            raise ExecutionAdapterTimeoutError(
                "timeout",
                audit_descriptor={
                    "provider": "fake-cloud",
                },
                stdout="partial",
                stderr="timeout",
            )

    with pytest.raises(
        RecoveryExecutionError
    ) as exc_info:
        execute_recovery_action(
            DECISION,
            dry_run=False,
            execution_adapter=TimeoutAdapter(),
        )

    details = exc_info.value.details

    assert details["failure_type"] == "TIMEOUT"
    assert details["timeout_seconds"] == 180
    assert details["failed_command"] == {
        "provider": "fake-cloud",
    }
