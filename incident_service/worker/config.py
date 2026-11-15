import os
from dataclasses import dataclass


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be a boolean value."
    )


@dataclass(frozen=True)
class WorkerConfig:
    poll_interval_seconds: float = 10.0
    max_incidents_per_cycle: int = 1
    dry_run: bool = True
    max_autonomous_attempts: int = 3
    queue_claim_seconds: int = 300
    queue_claim_heartbeat_interval_seconds: float = 60.0
    retry_base_seconds: int = 60
    retry_max_seconds: int = 1800

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        poll_interval_seconds = float(
            os.getenv(
                "INCIDENT_WORKER_POLL_INTERVAL_SECONDS",
                "10",
            )
        )

        max_incidents_per_cycle = int(
            os.getenv(
                "INCIDENT_WORKER_MAX_INCIDENTS_PER_CYCLE",
                "1",
            )
        )

        dry_run = _read_bool(
            "INCIDENT_WORKER_DRY_RUN",
            True,
        )
        max_autonomous_attempts = int(
            os.getenv(
                "INCIDENT_WORKER_MAX_AUTONOMOUS_ATTEMPTS",
                "3",
            )
        )
        queue_claim_seconds = int(
            os.getenv(
                "INCIDENT_WORKER_QUEUE_CLAIM_SECONDS",
                "300",
            )
        )
        queue_claim_heartbeat_interval_seconds = float(
            os.getenv(
                "INCIDENT_WORKER_QUEUE_HEARTBEAT_INTERVAL_SECONDS",
                "60",
            )
        )
        retry_base_seconds = int(
            os.getenv(
                "INCIDENT_WORKER_RETRY_BASE_SECONDS",
                "60",
            )
        )
        retry_max_seconds = int(
            os.getenv(
                "INCIDENT_WORKER_RETRY_MAX_SECONDS",
                "1800",
            )
        )

        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than 0."
            )

        if max_incidents_per_cycle <= 0:
            raise ValueError(
                "max_incidents_per_cycle must be greater than 0."
            )

        if max_autonomous_attempts <= 0:
            raise ValueError(
                "max_autonomous_attempts must be greater than 0."
            )
        if queue_claim_seconds <= 0:
            raise ValueError(
                "queue_claim_seconds must be greater than 0."
            )
        if queue_claim_heartbeat_interval_seconds <= 0:
            raise ValueError(
                "queue claim heartbeat interval must be greater than 0."
            )
        if queue_claim_heartbeat_interval_seconds >= queue_claim_seconds:
            raise ValueError(
                "queue claim heartbeat interval must be shorter than the claim lease."
            )
        if retry_base_seconds <= 0:
            raise ValueError(
                "retry_base_seconds must be greater than 0."
            )
        if retry_max_seconds <= 0:
            raise ValueError(
                "retry_max_seconds must be greater than 0."
            )
        if retry_base_seconds > retry_max_seconds:
            raise ValueError(
                "retry_base_seconds must not exceed retry_max_seconds."
            )
        return cls(
            poll_interval_seconds=poll_interval_seconds,
            max_incidents_per_cycle=max_incidents_per_cycle,
            dry_run=dry_run,
            max_autonomous_attempts=max_autonomous_attempts,
            queue_claim_seconds=queue_claim_seconds,
            queue_claim_heartbeat_interval_seconds=queue_claim_heartbeat_interval_seconds,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )
