from threading import Event
from typing import Callable, Optional

from incident_service.repository import (
    get_automation_candidates,
)
from incident_service.recovery.orchestrator import (
    recover_incident,
)
from incident_service.worker.config import WorkerConfig


def run_cycle(
    provider: Callable,
    config: Optional[WorkerConfig] = None,
) -> dict:
    """
    Process one autonomous incident-worker cycle.

    Candidate selection decides which incidents may be investigated.
    The Phase 3 recovery orchestrator remains responsible for
    recovery policy, ownership, fencing, execution, and validation.
    """
    config = config or WorkerConfig.from_env()

    candidates = get_automation_candidates(
        limit=config.max_incidents_per_cycle,
    )

    if not candidates:
        return {
            "status": "IDLE",
            "candidate_count": 0,
            "processed": [],
        }

    processed = []

    for incident in candidates:
        incident_id = incident["incident_id"]

        try:
            result = recover_incident(
                incident_id=incident_id,
                provider=provider,
                dry_run=config.dry_run,
            )

            processed.append(
                {
                    "incident_id": incident_id,
                    "status": "PROCESSED",
                    "result": result,
                }
            )

        except Exception as exc:
            processed.append(
                {
                    "incident_id": incident_id,
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    return {
        "status": "COMPLETED",
        "candidate_count": len(candidates),
        "processed": processed,
    }


def run_forever(
    provider: Callable,
    config: Optional[WorkerConfig] = None,
    stop_event: Optional[Event] = None,
) -> None:
    """
    Continuously poll for automation-eligible incidents.

    stop_event allows the worker to shut down cleanly without
    waiting for the full polling interval to expire.
    """
    config = config or WorkerConfig.from_env()
    stop_event = stop_event or Event()

    while not stop_event.is_set():
        result = run_cycle(
            provider=provider,
            config=config,
        )

        print(result, flush=True)

        stop_event.wait(
            config.poll_interval_seconds
        )
