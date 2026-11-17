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
from incident_service.recovery.adapters.config import (
    RecoveryExecutionConfig,
)
from incident_service.recovery.adapters.emr_serverless import (
    EMRServerlessExecutionAdapter,
)
from incident_service.recovery.adapters.factory import (
    build_execution_adapter,
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


def test_execution_adapter_factory_defaults_to_local_docker(
    monkeypatch,
):
    monkeypatch.delenv(
        "RECOVERY_EXECUTION_BACKEND",
        raising=False,
    )

    adapter = build_execution_adapter()

    assert isinstance(
        adapter,
        LocalDockerExecutionAdapter,
    )
    assert adapter.name == "local-docker"


def test_emr_serverless_factory_is_lazy_for_preview():
    config = RecoveryExecutionConfig(
        backend="emr-serverless",
        aws_region="us-east-1",
        emr_serverless_application_id="00example",
        emr_serverless_execution_role_arn=(
            "arn:aws:iam::123456789012:"
            "role/example-emr-role"
        ),
        emr_serverless_artifact_bucket=(
            "example-recovery-bucket"
        ),
        emr_serverless_artifact_prefix=(
            "incident-recovery"
        ),
    )

    adapter = build_execution_adapter(config)

    assert isinstance(
        adapter,
        EMRServerlessExecutionAdapter,
    )

    assert adapter._s3_client is None
    assert adapter._emr_client is None

    preview = adapter.preview_step(
        ExecutionStep(
            operation="RUN_SPARK_SCRIPT",
            parameters={
                "script_path":
                    "/tmp/restore_schema_drift.py",
            },
        )
    )

    assert preview["entry_point"] == (
        "s3://example-recovery-bucket/"
        "incident-recovery/scripts/"
        "restore_schema_drift.py"
    )

    assert adapter._s3_client is None
    assert adapter._emr_client is None


def test_emr_serverless_stages_artifact_to_s3(
    tmp_path,
):
    class FakeS3Client:
        def __init__(self):
            self.upload = None

        def upload_file(
            self,
            source,
            bucket,
            key,
        ):
            self.upload = {
                "source": source,
                "bucket": bucket,
                "key": key,
            }

    class FakeEMRClient:
        pass

    source = (
        tmp_path
        / "restore_schema_drift.py"
    )

    source.write_text(
        "print('recovery')\n"
    )

    s3_client = FakeS3Client()

    adapter = EMRServerlessExecutionAdapter(
        application_id="00example",
        execution_role_arn=(
            "arn:aws:iam::123456789012:"
            "role/example-emr-role"
        ),
        artifact_bucket=(
            "example-recovery-bucket"
        ),
        s3_client=s3_client,
        emr_client=FakeEMRClient(),
    )

    result = adapter.execute_step(
        ExecutionStep(
            operation="STAGE_FILE",
            parameters={
                "source_path": str(source),
                "destination_path":
                    "/tmp/restore_schema_drift.py",
            },
        ),
        timeout_seconds=180,
    )

    assert result.returncode == 0

    assert s3_client.upload == {
        "source": str(source),
        "bucket":
            "example-recovery-bucket",
        "key": (
            "incident-recovery/scripts/"
            "restore_schema_drift.py"
        ),
    }


def test_emr_serverless_submits_and_completes_job():
    class FakeS3Client:
        pass

    class FakeEMRClient:
        def __init__(self):
            self.start_request = None
            self.get_request = None

        def start_job_run(self, **kwargs):
            self.start_request = kwargs

            return {
                "jobRunId": "jr-example",
            }

        def get_job_run(
            self,
            *,
            applicationId,
            jobRunId,
        ):
            self.get_request = {
                "applicationId":
                    applicationId,
                "jobRunId":
                    jobRunId,
            }

            return {
                "jobRun": {
                    "state": "SUCCESS",
                    "stateDetails": "",
                }
            }

    emr_client = FakeEMRClient()

    adapter = EMRServerlessExecutionAdapter(
        application_id="00example",
        execution_role_arn=(
            "arn:aws:iam::123456789012:"
            "role/example-emr-role"
        ),
        artifact_bucket=(
            "example-recovery-bucket"
        ),
        s3_client=FakeS3Client(),
        emr_client=emr_client,
    )

    result = adapter.execute_step(
        ExecutionStep(
            operation="RUN_SPARK_SCRIPT",
            parameters={
                "script_path":
                    "/tmp/restore_schema_drift.py",
            },
        ),
        timeout_seconds=180,
    )

    assert result.returncode == 0

    assert (
        emr_client.start_request[
            "applicationId"
        ]
        == "00example"
    )

    assert (
        emr_client.start_request[
            "executionRoleArn"
        ]
        == (
            "arn:aws:iam::123456789012:"
            "role/example-emr-role"
        )
    )

    assert (
        emr_client.start_request[
            "jobDriver"
        ]["sparkSubmit"]["entryPoint"]
        == (
            "s3://example-recovery-bucket/"
            "incident-recovery/scripts/"
            "restore_schema_drift.py"
        )
    )

    assert (
        emr_client.start_request[
            "configurationOverrides"
        ]["monitoringConfiguration"][
            "s3MonitoringConfiguration"
        ]["logUri"]
        == (
            "s3://example-recovery-bucket/"
            "incident-recovery/logs/"
        )
    )

    assert emr_client.get_request == {
        "applicationId": "00example",
        "jobRunId": "jr-example",
    }

    assert (
        result.audit_descriptor[
            "job_run_id"
        ]
        == "jr-example"
    )
