import shlex
import time

from pathlib import Path
from typing import Any

import boto3

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

from incident_service.recovery.adapters.base import (
    ExecutionAdapterError,
    ExecutionAdapterTimeoutError,
    ExecutionStep,
    ExecutionStepResult,
)
from incident_service.recovery.adapters.config import (
    RecoveryExecutionConfig,
)


TERMINAL_JOB_STATES = {
    "SUCCESS",
    "FAILED",
    "CANCELLED",
}

DEFAULT_POLL_INTERVAL_SECONDS = 2.0


class EMRServerlessExecutionAdapter:
    """
    Execute provider-neutral recovery steps through
    Amazon EMR Serverless.

    STAGE_FILE uploads a local recovery artifact to S3.
    RUN_SPARK_SCRIPT submits the staged artifact as an
    EMR Serverless Spark job and waits for completion.
    """

    name = "emr-serverless"

    def __init__(
        self,
        *,
        application_id: str,
        execution_role_arn: str,
        artifact_bucket: str,
        artifact_prefix: str = "incident-recovery",
        aws_region: str = "us-east-1",
        poll_interval_seconds: float = (
            DEFAULT_POLL_INTERVAL_SECONDS
        ),
        s3_client: Any = None,
        emr_client: Any = None,
    ) -> None:
        if not application_id:
            raise ValueError(
                "application_id must not be empty."
            )

        if not execution_role_arn:
            raise ValueError(
                "execution_role_arn must not be empty."
            )

        if not artifact_bucket:
            raise ValueError(
                "artifact_bucket must not be empty."
            )

        artifact_prefix = (
            artifact_prefix.strip().strip("/")
        )

        if not artifact_prefix:
            raise ValueError(
                "artifact_prefix must not be empty."
            )

        if not aws_region:
            raise ValueError(
                "aws_region must not be empty."
            )

        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be "
                "greater than 0."
            )

        self.application_id = application_id
        self.execution_role_arn = execution_role_arn
        self.artifact_bucket = artifact_bucket
        self.artifact_prefix = artifact_prefix
        self.aws_region = aws_region
        self.poll_interval_seconds = (
            poll_interval_seconds
        )

        # Keep AWS clients lazy so imports and dry-run
        # previews never trigger credential discovery or
        # network-related AWS behavior.
        self._s3_client = s3_client
        self._emr_client = emr_client

    @property
    def s3_client(self) -> Any:
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                region_name=self.aws_region,
            )

        return self._s3_client

    @property
    def emr_client(self) -> Any:
        if self._emr_client is None:
            self._emr_client = boto3.client(
                "emr-serverless",
                region_name=self.aws_region,
            )

        return self._emr_client

    @classmethod
    def from_config(
        cls,
        config: RecoveryExecutionConfig,
        **kwargs: Any,
    ) -> "EMRServerlessExecutionAdapter":
        if config.backend != "emr-serverless":
            raise ValueError(
                "RecoveryExecutionConfig backend must "
                "be emr-serverless."
            )

        return cls(
            application_id=(
                config.emr_serverless_application_id
                or ""
            ),
            execution_role_arn=(
                config.emr_serverless_execution_role_arn
                or ""
            ),
            artifact_bucket=(
                config.emr_serverless_artifact_bucket
                or ""
            ),
            artifact_prefix=(
                config.emr_serverless_artifact_prefix
            ),
            aws_region=config.aws_region,
            **kwargs,
        )

    def _script_key(
        self,
        script_path: str,
    ) -> str:
        filename = Path(script_path).name

        if not filename:
            raise ExecutionAdapterError(
                "Unable to determine recovery "
                "artifact filename.",
                audit_descriptor={
                    "operation": "STAGE_FILE",
                    "script_path": script_path,
                },
            )

        return (
            f"{self.artifact_prefix}/scripts/"
            f"{filename}"
        )

    def _script_uri(
        self,
        script_path: str,
    ) -> str:
        key = self._script_key(script_path)

        return (
            f"s3://{self.artifact_bucket}/{key}"
        )

    def _log_uri(self) -> str:
        return (
            f"s3://{self.artifact_bucket}/"
            f"{self.artifact_prefix}/logs/"
        )

    def _build_spark_submit_parameters(
        self,
        step: ExecutionStep,
    ) -> str:
        # Keep recovery jobs deliberately small by
        # default. EMR Serverless otherwise starts with
        # substantially larger Spark driver/executor
        # resources.
        #
        # Callers can append explicit Spark settings below
        # when a recovery workload genuinely needs more.
        parts: list[str] = [
            "--conf",
            "spark.driver.cores=1",
            "--conf",
            "spark.driver.memory=4g",
            "--conf",
            "spark.executor.cores=1",
            "--conf",
            "spark.executor.memory=4g",
            "--conf",
            "spark.executor.instances=1",
            "--conf",
            "spark.dynamicAllocation.enabled=false",
        ]

        packages = step.parameters.get(
            "packages"
        )

        if packages:
            parts.extend(
                [
                    "--packages",
                    str(packages),
                ]
            )

        spark_conf = step.parameters.get(
            "spark_conf",
            (),
        )

        for conf in spark_conf:
            parts.extend(
                [
                    "--conf",
                    str(conf),
                ]
            )

        environment = step.parameters.get(
            "environment",
            {},
        )

        for key, value in sorted(
            environment.items()
        ):
            parts.extend(
                [
                    "--conf",
                    (
                        "spark.emr-serverless."
                        f"driverEnv.{key}={value}"
                    ),
                ]
            )

        return shlex.join(parts)

    def _build_stage_descriptor(
        self,
        step: ExecutionStep,
    ) -> dict[str, Any]:
        source_path = str(
            step.parameters["source_path"]
        )

        destination_path = str(
            step.parameters["destination_path"]
        )

        return {
            "backend": self.name,
            "operation": "STAGE_FILE",
            "source_path": source_path,
            "destination_uri": self._script_uri(
                destination_path
            ),
        }

    def _build_job_descriptor(
        self,
        step: ExecutionStep,
    ) -> dict[str, Any]:
        script_path = str(
            step.parameters["script_path"]
        )

        descriptor: dict[str, Any] = {
            "backend": self.name,
            "operation": "RUN_SPARK_SCRIPT",
            "application_id":
                self.application_id,
            "entry_point":
                self._script_uri(script_path),
            "log_uri": self._log_uri(),
        }

        spark_submit_parameters = (
            self._build_spark_submit_parameters(
                step
            )
        )

        if spark_submit_parameters:
            descriptor[
                "spark_submit_parameters"
            ] = spark_submit_parameters

        entry_point_arguments = (
            step.parameters.get(
                "entry_point_arguments"
            )
        )

        if entry_point_arguments:
            descriptor[
                "entry_point_arguments"
            ] = [
                str(value)
                for value
                in entry_point_arguments
            ]

        return descriptor

    def preview_step(
        self,
        step: ExecutionStep,
    ) -> Any:
        if step.operation == "STAGE_FILE":
            return self._build_stage_descriptor(
                step
            )

        if step.operation == "RUN_SPARK_SCRIPT":
            return self._build_job_descriptor(
                step
            )

        if step.operation == "FETCH_FILE":
            source_path = str(
                step.parameters["source_path"]
            )

            destination_path = str(
                step.parameters[
                    "destination_path"
                ]
            )

            return {
                "backend": self.name,
                "operation": "FETCH_FILE",
                "source_uri": source_path,
                "destination_path":
                    destination_path,
            }

        raise ExecutionAdapterError(
            "Unsupported EMR Serverless execution "
            f"operation: {step.operation}",
            audit_descriptor={
                "operation": step.operation,
                "parameters": step.parameters,
            },
        )

    def _execute_stage_file(
        self,
        step: ExecutionStep,
    ) -> ExecutionStepResult:
        descriptor = (
            self._build_stage_descriptor(step)
        )

        source_path = Path(
            step.parameters["source_path"]
        )

        if not source_path.is_file():
            raise ExecutionAdapterError(
                "Recovery artifact was not found.",
                audit_descriptor=descriptor,
                stderr=str(source_path),
            )

        destination_path = str(
            step.parameters["destination_path"]
        )

        key = self._script_key(
            destination_path
        )

        try:
            self.s3_client.upload_file(
                str(source_path),
                self.artifact_bucket,
                key,
            )

        except (
            BotoCoreError,
            ClientError,
            S3UploadFailedError,
        ) as exc:
            raise ExecutionAdapterError(
                "Failed to stage recovery artifact "
                "in S3.",
                audit_descriptor=descriptor,
                stderr=str(exc),
            ) from exc

        return ExecutionStepResult(
            audit_descriptor=descriptor,
            returncode=0,
            stdout=(
                "Recovery artifact staged at "
                f"{descriptor['destination_uri']}."
            ),
            stderr="",
        )

    def _execute_spark_job(
        self,
        step: ExecutionStep,
        *,
        timeout_seconds: int,
    ) -> ExecutionStepResult:
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be "
                "greater than 0."
            )

        descriptor = (
            self._build_job_descriptor(step)
        )

        spark_submit: dict[str, Any] = {
            "entryPoint":
                descriptor["entry_point"],
        }

        spark_submit_parameters = (
            descriptor.get(
                "spark_submit_parameters"
            )
        )

        if spark_submit_parameters:
            spark_submit[
                "sparkSubmitParameters"
            ] = spark_submit_parameters

        entry_point_arguments = (
            descriptor.get(
                "entry_point_arguments"
            )
        )

        if entry_point_arguments:
            spark_submit[
                "entryPointArguments"
            ] = entry_point_arguments

        script_name = Path(
            str(
                step.parameters[
                    "script_path"
                ]
            )
        ).stem

        job_name = (
            f"incident-recovery-{script_name}"
        )[:64]

        request = {
            "applicationId":
                self.application_id,
            "executionRoleArn":
                self.execution_role_arn,
            "name": job_name,
            "jobDriver": {
                "sparkSubmit": spark_submit,
            },
            "configurationOverrides": {
                "monitoringConfiguration": {
                    "s3MonitoringConfiguration": {
                        "logUri":
                            self._log_uri(),
                    },
                },
            },
        }

        try:
            response = (
                self.emr_client.start_job_run(
                    **request
                )
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise ExecutionAdapterError(
                "Failed to submit EMR Serverless "
                "recovery job.",
                audit_descriptor=descriptor,
                stderr=str(exc),
            ) from exc

        job_run_id = response.get(
            "jobRunId"
        )

        if not job_run_id:
            raise ExecutionAdapterError(
                "EMR Serverless did not return "
                "a job run ID.",
                audit_descriptor=descriptor,
            )

        execution_descriptor = {
            **descriptor,
            "job_run_id": job_run_id,
        }

        deadline = (
            time.monotonic()
            + timeout_seconds
        )

        while True:
            try:
                response = (
                    self.emr_client.get_job_run(
                        applicationId=(
                            self.application_id
                        ),
                        jobRunId=job_run_id,
                    )
                )

            except (
                BotoCoreError,
                ClientError,
            ) as exc:
                raise ExecutionAdapterError(
                    "Failed while monitoring EMR "
                    "Serverless recovery job.",
                    audit_descriptor=(
                        execution_descriptor
                    ),
                    stderr=str(exc),
                ) from exc

            job_run = response.get(
                "jobRun",
                {},
            )

            state = job_run.get(
                "state",
                "UNKNOWN",
            )

            state_details = job_run.get(
                "stateDetails",
                "",
            )

            if state == "SUCCESS":
                return ExecutionStepResult(
                    audit_descriptor={
                        **execution_descriptor,
                        "state": state,
                    },
                    returncode=0,
                    stdout=(
                        "EMR Serverless recovery "
                        f"job {job_run_id} "
                        "completed successfully."
                    ),
                    stderr="",
                )

            if state in {
                "FAILED",
                "CANCELLED",
            }:
                raise ExecutionAdapterError(
                    "EMR Serverless recovery job "
                    f"ended in state {state}.",
                    audit_descriptor={
                        **execution_descriptor,
                        "state": state,
                    },
                    returncode=1,
                    stderr=state_details,
                )

            if time.monotonic() >= deadline:
                cancellation_error = ""

                try:
                    self.emr_client.cancel_job_run(
                        applicationId=(
                            self.application_id
                        ),
                        jobRunId=job_run_id,
                    )

                except (
                    BotoCoreError,
                    ClientError,
                ) as exc:
                    cancellation_error = (
                        " Cancellation request "
                        f"failed: {exc}"
                    )

                raise (
                    ExecutionAdapterTimeoutError(
                        "EMR Serverless recovery "
                        "job timed out.",
                        audit_descriptor={
                            **execution_descriptor,
                            "state": state,
                        },
                        stderr=(
                            f"{state_details}"
                            f"{cancellation_error}"
                        ).strip(),
                    )
                )

            time.sleep(
                self.poll_interval_seconds
            )

    def _execute_fetch_file(
        self,
        step: ExecutionStep,
    ) -> ExecutionStepResult:
        descriptor = self.preview_step(step)

        source_uri = str(
            step.parameters["source_path"]
        )

        if not source_uri.startswith("s3://"):
            raise ExecutionAdapterError(
                "EMR Serverless FETCH_FILE "
                "requires an s3:// source URI.",
                audit_descriptor=descriptor,
            )

        remainder = source_uri[5:]

        bucket, separator, key = (
            remainder.partition("/")
        )

        if (
            not bucket
            or not separator
            or not key
        ):
            raise ExecutionAdapterError(
                "Invalid S3 source URI.",
                audit_descriptor=descriptor,
            )

        destination_path = Path(
            str(
                step.parameters[
                    "destination_path"
                ]
            )
        )

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            self.s3_client.download_file(
                bucket,
                key,
                str(destination_path),
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise ExecutionAdapterError(
                "Failed to fetch recovery "
                "artifact from S3.",
                audit_descriptor=descriptor,
                stderr=str(exc),
            ) from exc

        return ExecutionStepResult(
            audit_descriptor=descriptor,
            returncode=0,
            stdout=(
                "Recovery artifact fetched from "
                f"{source_uri}."
            ),
            stderr="",
        )

    def execute_step(
        self,
        step: ExecutionStep,
        *,
        timeout_seconds: int,
    ) -> ExecutionStepResult:
        if step.operation == "STAGE_FILE":
            return self._execute_stage_file(
                step
            )

        if step.operation == "RUN_SPARK_SCRIPT":
            return self._execute_spark_job(
                step,
                timeout_seconds=timeout_seconds,
            )

        if step.operation == "FETCH_FILE":
            return self._execute_fetch_file(
                step
            )

        raise ExecutionAdapterError(
            "Unsupported EMR Serverless execution "
            f"operation: {step.operation}",
            audit_descriptor={
                "operation": step.operation,
                "parameters": step.parameters,
            },
        )
