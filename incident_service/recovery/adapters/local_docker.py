import subprocess
from typing import Any

from incident_service.recovery.adapters.base import (
    ExecutionAdapterError,
    ExecutionAdapterTimeoutError,
    ExecutionStep,
    ExecutionStepResult,
)


SPARK_CONTAINER = "incident-platform-spark"

SPARK_SUBMIT = "/opt/spark/bin/spark-submit"

SPARK_PACKAGES = (
    "org.apache.hadoop:hadoop-aws:3.3.4,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.262"
)

DEFAULT_SPARK_CONF = (
    "spark.driver.extraJavaOptions="
    "-Divy.cache.dir=/tmp/.ivy2",
    "spark.jars.ivy=/tmp/.ivy2",
)


def _normalize_output(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(
            errors="replace"
        ).strip()

    return str(value).strip()


class LocalDockerExecutionAdapter:
    """
    Execute provider-neutral recovery steps through
    the current local Docker + Spark runtime.

    This adapter preserves the Phase 3/4 execution
    mechanism while isolating Docker-specific details
    from the recovery orchestration layer.
    """

    name = "local-docker"

    def __init__(
        self,
        *,
        spark_container: str = SPARK_CONTAINER,
        spark_submit: str = SPARK_SUBMIT,
        spark_packages: str = SPARK_PACKAGES,
    ) -> None:
        self.spark_container = spark_container
        self.spark_submit = spark_submit
        self.spark_packages = spark_packages

    def _build_command(
        self,
        step: ExecutionStep,
    ) -> list[str]:
        if step.operation == "STAGE_FILE":
            source_path = step.parameters[
                "source_path"
            ]
            destination_path = step.parameters[
                "destination_path"
            ]

            return [
                "docker",
                "cp",
                str(source_path),
                (
                    f"{self.spark_container}:"
                    f"{destination_path}"
                ),
            ]

        if step.operation == "RUN_SPARK_SCRIPT":
            script_path = step.parameters[
                "script_path"
            ]
            packages = step.parameters.get(
                "packages",
                self.spark_packages,
            )
            spark_conf = step.parameters.get(
                "spark_conf",
                DEFAULT_SPARK_CONF,
            )

            command = [
                "docker",
                "exec",
                self.spark_container,
                self.spark_submit,
            ]

            if packages:
                command.extend(
                    [
                        "--packages",
                        packages,
                    ]
                )

            for conf in spark_conf:
                command.extend(
                    [
                        "--conf",
                        conf,
                    ]
                )

            command.append(
                str(script_path)
            )

            return command

        raise ExecutionAdapterError(
            "Unsupported local Docker execution "
            f"operation: {step.operation}",
            audit_descriptor={
                "operation": step.operation,
                "parameters": step.parameters,
            },
        )

    def preview_step(
        self,
        step: ExecutionStep,
    ) -> Any:
        return self._build_command(step)

    def execute_step(
        self,
        step: ExecutionStep,
        *,
        timeout_seconds: int,
    ) -> ExecutionStepResult:
        command = self._build_command(step)

        try:
            completed = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )

        except subprocess.TimeoutExpired as exc:
            raise ExecutionAdapterTimeoutError(
                "Local Docker execution timed out.",
                audit_descriptor=command,
                stdout=_normalize_output(
                    exc.stdout
                ),
                stderr=_normalize_output(
                    exc.stderr
                ),
            ) from exc

        except subprocess.CalledProcessError as exc:
            raise ExecutionAdapterError(
                "Local Docker execution failed.",
                audit_descriptor=command,
                returncode=exc.returncode,
                stdout=_normalize_output(
                    exc.stdout
                ),
                stderr=_normalize_output(
                    exc.stderr
                ),
            ) from exc

        return ExecutionStepResult(
            audit_descriptor=command,
            returncode=completed.returncode,
            stdout=_normalize_output(
                completed.stdout
            ),
            stderr=_normalize_output(
                completed.stderr
            ),
        )
