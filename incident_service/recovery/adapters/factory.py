from incident_service.recovery.adapters.base import (
    RecoveryExecutionAdapter,
)
from incident_service.recovery.adapters.config import (
    RecoveryExecutionConfig,
)
from incident_service.recovery.adapters.local_docker import (
    LocalDockerExecutionAdapter,
)


def build_execution_adapter(
    config: RecoveryExecutionConfig | None = None,
) -> RecoveryExecutionAdapter:
    """
    Build the configured recovery execution backend.

    Local Docker remains the safe/default backend.
    Cloud-specific adapters are imported only when
    explicitly selected.
    """

    resolved = (
        config
        if config is not None
        else RecoveryExecutionConfig.from_env()
    )

    if resolved.backend == "local-docker":
        return LocalDockerExecutionAdapter()

    if resolved.backend == "emr-serverless":
        from incident_service.recovery.adapters.emr_serverless import (
            EMRServerlessExecutionAdapter,
        )

        return EMRServerlessExecutionAdapter.from_config(
            resolved
        )

    # RecoveryExecutionConfig already validates this,
    # but keep the factory defensive if a config object
    # is constructed directly.
    raise ValueError(
        "Unsupported recovery execution backend: "
        f"{resolved.backend}"
    )
