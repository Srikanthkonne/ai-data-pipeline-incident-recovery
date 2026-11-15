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

        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than 0."
            )

        if max_incidents_per_cycle <= 0:
            raise ValueError(
                "max_incidents_per_cycle must be greater than 0."
            )

        return cls(
            poll_interval_seconds=poll_interval_seconds,
            max_incidents_per_cycle=max_incidents_per_cycle,
            dry_run=dry_run,
        )
