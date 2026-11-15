from threading import Event, Thread
from typing import Callable, Optional
from uuid import uuid4

from incident_service.repository import (
    get_automation_candidates,
)
from incident_service.recovery.orchestrator import (
    recover_incident,
)
from incident_service.recovery.queue_repository import (
    claim_next_recovery,
    enqueue_recovery,
    mark_recovery_queue_completed,
    mark_recovery_queue_terminal,
    refresh_recovery_queue_claim,
    release_recovery_queue_claim,
    schedule_recovery_retry,
)
from incident_service.recovery.retry_policy import (
    calculate_retry_backoff_seconds,
    classify_recovery_outcome,
    get_result_error,
)
from incident_service.worker.config import WorkerConfig


class _QueueClaimHeartbeat:
    def __init__(
        self,
        incident_id: int,
        claim_token: str,
        claim_seconds: int,
        interval_seconds: float,
    ) -> None:
        self.incident_id = incident_id
        self.claim_token = claim_token
        self.claim_seconds = claim_seconds
        self.interval_seconds = interval_seconds
        self._stop_event = Event()
        self._thread = Thread(
            target=self._run,
            daemon=True,
        )
        self.claim_lost = False
        self.error = None

    def _run(self) -> None:
        while not self._stop_event.wait(
            self.interval_seconds
        ):
            try:
                refreshed = refresh_recovery_queue_claim(
                    incident_id=self.incident_id,
                    claim_token=self.claim_token,
                    claim_seconds=self.claim_seconds,
                )
            except Exception as exc:
                self.claim_lost = True
                self.error = (
                    f"{type(exc).__name__}: {exc}"
                )
                return

            if refreshed is None:
                self.claim_lost = True
                return

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(
            timeout=self.interval_seconds + 1
        )


def run_cycle(
    provider: Callable,
    config: Optional[WorkerConfig] = None,
) -> dict:
    config = config or WorkerConfig.from_env()

    candidates = get_automation_candidates(
        limit=config.max_incidents_per_cycle,
    )

    seeded = []

    for incident in candidates:
        incident_id = incident["incident_id"]

        try:
            queue_item = enqueue_recovery(
                incident_id=incident_id,
                max_attempts=(
                    config.max_autonomous_attempts
                ),
            )
            seeded.append(
                {
                    "incident_id": incident_id,
                    "status": "ENQUEUED",
                    "queue_state": queue_item["state"],
                }
            )
        except Exception as exc:
            seeded.append(
                {
                    "incident_id": incident_id,
                    "status": "ENQUEUE_ERROR",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    processed = []

    for _ in range(
        config.max_incidents_per_cycle
    ):
        claim_token = (
            f"worker-{uuid4()}"
        )

        queue_item = claim_next_recovery(
            claim_token=claim_token,
            claim_seconds=(
                config.queue_claim_seconds
            ),
        )

        if queue_item is None:
            break

        incident_id = queue_item["incident_id"]

        heartbeat = _QueueClaimHeartbeat(
            incident_id=incident_id,
            claim_token=claim_token,
            claim_seconds=(
                config.queue_claim_seconds
            ),
            interval_seconds=(
                config
                .queue_claim_heartbeat_interval_seconds
            ),
        )

        heartbeat_started = False
        result = None
        worker_error = None

        try:
            heartbeat.start()
            heartbeat_started = True

            result = recover_incident(
                incident_id=incident_id,
                provider=provider,
                dry_run=config.dry_run,
            )

        except Exception as exc:
            worker_error = exc

        finally:
            if heartbeat_started:
                heartbeat.stop()

        if heartbeat.claim_lost:
            processed.append(
                {
                    "incident_id": incident_id,
                    "status": "CLAIM_LOST",
                    "queue_state": "PROCESSING",
                    "heartbeat_error":
                        heartbeat.error,
                    "worker_error": (
                        None
                        if worker_error is None
                        else (
                            f"{type(worker_error).__name__}: "
                            f"{worker_error}"
                        )
                    ),
                }
            )
            continue

        attempt_count = int(
            queue_item[
                "autonomous_attempt_count"
            ]
        )

        if worker_error is not None:
            error_message = (
                f"{type(worker_error).__name__}: "
                f"{worker_error}"
            )

            backoff_seconds = (
                calculate_retry_backoff_seconds(
                    attempt_count,
                    base_seconds=(
                        config.retry_base_seconds
                    ),
                    max_seconds=(
                        config.retry_max_seconds
                    ),
                )
            )

            transitioned = (
                schedule_recovery_retry(
                    incident_id=incident_id,
                    claim_token=claim_token,
                    recovery_attempt_id=None,
                    attempt_status="WORKER_ERROR",
                    backoff_seconds=(
                        backoff_seconds
                    ),
                    error_message=error_message,
                )
            )

            processed.append(
                {
                    "incident_id": incident_id,
                    "status": (
                        "WORKER_ERROR"
                        if transitioned
                        else "CLAIM_LOST"
                    ),
                    "queue_state": (
                        transitioned["state"]
                        if transitioned
                        else None
                    ),
                    "backoff_seconds":
                        backoff_seconds,
                    "error": error_message,
                }
            )
            continue

        orchestration_status = str(
            result.get(
                "orchestration_status"
            )
            or "WORKER_ERROR"
        ).strip().upper()

        recovery_attempt_id = result.get(
            "recovery_attempt_id"
        )

        error_message = get_result_error(
            result
        )

        if (
            orchestration_status
            == "WORKER_ERROR"
            and error_message is None
        ):
            error_message = (
                "recover_incident returned no "
                "orchestration_status."
            )

        if config.dry_run:
            transitioned = (
                release_recovery_queue_claim(
                    incident_id=incident_id,
                    claim_token=claim_token,
                    recovery_attempt_id=(
                        recovery_attempt_id
                    ),
                    attempt_status=(
                        orchestration_status
                    ),
                )
            )

            processed.append(
                {
                    "incident_id": incident_id,
                    "status": (
                        "DRY_RUN_RELEASED"
                        if transitioned
                        else "CLAIM_LOST"
                    ),
                    "orchestration_status":
                        orchestration_status,
                    "recovery_attempt_id":
                        recovery_attempt_id,
                    "queue_state": (
                        transitioned["state"]
                        if transitioned
                        else None
                    ),
                    "result": result,
                }
            )
            continue

        classification = (
            classify_recovery_outcome(
                orchestration_status
            )
        )

        if classification == "RETRY":
            backoff_seconds = (
                calculate_retry_backoff_seconds(
                    attempt_count,
                    base_seconds=(
                        config.retry_base_seconds
                    ),
                    max_seconds=(
                        config.retry_max_seconds
                    ),
                )
            )

            transitioned = (
                schedule_recovery_retry(
                    incident_id=incident_id,
                    claim_token=claim_token,
                    recovery_attempt_id=(
                        recovery_attempt_id
                    ),
                    attempt_status=(
                        orchestration_status
                    ),
                    backoff_seconds=(
                        backoff_seconds
                    ),
                    error_message=error_message,
                )
            )

        elif classification == "COMPLETED":
            backoff_seconds = None

            transitioned = (
                mark_recovery_queue_completed(
                    incident_id=incident_id,
                    claim_token=claim_token,
                    recovery_attempt_id=(
                        recovery_attempt_id
                    ),
                    attempt_status=(
                        orchestration_status
                    ),
                )
            )

        else:
            backoff_seconds = None

            transitioned = (
                mark_recovery_queue_terminal(
                    incident_id=incident_id,
                    claim_token=claim_token,
                    recovery_attempt_id=(
                        recovery_attempt_id
                    ),
                    attempt_status=(
                        orchestration_status
                    ),
                    error_message=error_message,
                )
            )

        processed.append(
            {
                "incident_id": incident_id,
                "status": (
                    transitioned["state"]
                    if transitioned
                    else "CLAIM_LOST"
                ),
                "orchestration_status":
                    orchestration_status,
                "recovery_attempt_id":
                    recovery_attempt_id,
                "queue_state": (
                    transitioned["state"]
                    if transitioned
                    else None
                ),
                "autonomous_attempt_count":
                    attempt_count,
                "backoff_seconds":
                    backoff_seconds,
                "error": error_message,
                "result": result,
            }
        )

    return {
        "status": (
            "IDLE"
            if not seeded and not processed
            else "COMPLETED"
        ),
        "candidate_count": len(candidates),
        "seeded": seeded,
        "processed": processed,
    }


def run_forever(
    provider: Callable,
    config: Optional[WorkerConfig] = None,
    stop_event: Optional[Event] = None,
) -> None:
    config = config or WorkerConfig.from_env()
    stop_event = stop_event or Event()

    if config.dry_run:
        result = run_cycle(
            provider=provider,
            config=config,
        )
        print(result, flush=True)
        return

    while not stop_event.is_set():
        result = run_cycle(
            provider=provider,
            config=config,
        )
        print(result, flush=True)
        stop_event.wait(
            config.poll_interval_seconds
        )
