from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ExecutionStep:
    """
    Provider-neutral description of one recovery
    execution step.

    The recovery layer defines WHAT should happen.
    A concrete adapter decides HOW and WHERE it runs.
    """

    operation: str
    parameters: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ExecutionStepResult:
    """
    Normalized result returned by an execution adapter.

    audit_descriptor preserves the adapter-specific
    representation used for audit/debugging. For the
    local Docker adapter this will remain the exact
    command list used today.
    """

    audit_descriptor: Any
    returncode: int
    stdout: str = ""
    stderr: str = ""


class ExecutionAdapterError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        audit_descriptor: Any = None,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.audit_descriptor = audit_descriptor
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ExecutionAdapterTimeoutError(
    ExecutionAdapterError
):
    pass


class RecoveryExecutionAdapter(Protocol):
    """
    Contract implemented by recovery execution
    backends.

    Phase 5A will provide the existing local Docker
    implementation. Future adapters can execute the
    same semantic recovery steps through managed
    cloud runtimes without changing orchestration.
    """

    name: str

    def preview_step(
        self,
        step: ExecutionStep,
    ) -> Any:
        """Return a safe audit representation."""
        ...

    def execute_step(
        self,
        step: ExecutionStep,
        *,
        timeout_seconds: int,
    ) -> ExecutionStepResult:
        """Execute one semantic recovery step."""
        ...
