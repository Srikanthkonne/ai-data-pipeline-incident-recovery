from uuid import uuid4

import pytest

from incident_service.db import get_db_connection
from incident_service.repository import create_incident
from incident_service.recovery.queue_repository import (
    enqueue_recovery,
    get_recovery_queue_item,
)
from incident_service.worker.config import WorkerConfig
import incident_service.worker.recovery_worker as recovery_worker


@pytest.fixture
def chaos_incident():
    test_id = uuid4().hex
    incident = create_incident(
        incident_type="PHASE4E_WORKER_CHAOS_TEST",
        dataset_name=f"phase4e.worker.{test_id}",
        source_system="pytest",
        severity="CRITICAL",
        title=f"Phase 4E worker chaos fixture {test_id}",
        description="Temporary worker failure-injection incident.",
        metadata={
            "automation_eligible": True,
            "phase4e_test": True,
        },
    )
    incident_id = incident["incident_id"]

    try:
        yield incident_id
    finally:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM recovery_queue WHERE incident_id = %s;",
                    (incident_id,),
                )
                cursor.execute(
                    "DELETE FROM recovery_attempts WHERE incident_id = %s;",
                    (incident_id,),
                )
                cursor.execute(
                    "DELETE FROM incidents WHERE incident_id = %s;",
                    (incident_id,),
                )
            conn.commit()
        finally:
            conn.close()


def worker_config(max_attempts: int = 3) -> WorkerConfig:
    return WorkerConfig(
        poll_interval_seconds=0.01,
        max_incidents_per_cycle=1,
        dry_run=False,
        max_autonomous_attempts=max_attempts,
        queue_claim_seconds=30,
        queue_claim_heartbeat_interval_seconds=5.0,
        retry_base_seconds=1,
        retry_max_seconds=4,
    )


def isolate_candidate_discovery(monkeypatch) -> None:
    monkeypatch.setattr(
        recovery_worker,
        "get_automation_candidates",
        lambda limit: [],
    )


@pytest.mark.parametrize(
    ("orchestration_status", "error_key"),
    [
        ("RCA_FAILED", "error"),
        ("EXECUTION_FAILED", "execution_error"),
        ("VALIDATION_FAILED", "validation_error"),
    ],
)
def test_retryable_outcome_moves_queue_to_retry_wait(
    chaos_incident,
    monkeypatch,
    orchestration_status,
    error_key,
):
    enqueue_recovery(chaos_incident, max_attempts=3)
    isolate_candidate_discovery(monkeypatch)

    def fake_recover_incident(**kwargs):
        return {
            "incident_id": chaos_incident,
            "recovery_attempt_id": None,
            "orchestration_status": orchestration_status,
            error_key: "controlled failure",
        }

    monkeypatch.setattr(
        recovery_worker,
        "recover_incident",
        fake_recover_incident,
    )

    result = recovery_worker.run_cycle(
        provider=lambda *args, **kwargs: None,
        config=worker_config(),
    )

    current = get_recovery_queue_item(chaos_incident)
    processed = result["processed"][0]

    assert current["state"] == "RETRY_WAIT"
    assert current["autonomous_attempt_count"] == 1
    assert current["last_attempt_status"] == orchestration_status
    assert current["last_error"] == "controlled failure"
    assert current["claim_token"] is None
    assert current["next_attempt_at"] is not None
    assert processed["status"] == "RETRY_WAIT"
    assert processed["orchestration_status"] == orchestration_status
    assert processed["backoff_seconds"] == 1


def test_unexpected_worker_exception_becomes_worker_error_retry(
    chaos_incident,
    monkeypatch,
):
    enqueue_recovery(chaos_incident, max_attempts=3)
    isolate_candidate_discovery(monkeypatch)

    def crashing_recovery(**kwargs):
        raise RuntimeError("controlled worker crash")

    monkeypatch.setattr(
        recovery_worker,
        "recover_incident",
        crashing_recovery,
    )

    result = recovery_worker.run_cycle(
        provider=lambda *args, **kwargs: None,
        config=worker_config(),
    )

    current = get_recovery_queue_item(chaos_incident)
    processed = result["processed"][0]

    assert current["state"] == "RETRY_WAIT"
    assert current["last_attempt_status"] == "WORKER_ERROR"
    assert "RuntimeError: controlled worker crash" in current["last_error"]
    assert processed["status"] == "WORKER_ERROR"
    assert processed["queue_state"] == "RETRY_WAIT"
    assert processed["backoff_seconds"] == 1


def test_final_retry_is_exhausted(
    chaos_incident,
    monkeypatch,
):
    enqueue_recovery(chaos_incident, max_attempts=1)
    isolate_candidate_discovery(monkeypatch)

    monkeypatch.setattr(
        recovery_worker,
        "recover_incident",
        lambda **kwargs: {
            "incident_id": chaos_incident,
            "recovery_attempt_id": None,
            "orchestration_status": "RCA_FAILED",
            "error": "controlled final failure",
        },
    )

    result = recovery_worker.run_cycle(
        provider=lambda *args, **kwargs: None,
        config=worker_config(max_attempts=1),
    )

    current = get_recovery_queue_item(chaos_incident)
    processed = result["processed"][0]

    assert current["state"] == "EXHAUSTED"
    assert current["autonomous_attempt_count"] == 1
    assert current["max_attempts"] == 1
    assert current["next_attempt_at"] is None
    assert current["last_attempt_status"] == "RCA_FAILED"
    assert processed["status"] == "EXHAUSTED"


@pytest.mark.parametrize(
    "orchestration_status",
    [
        "POLICY_FAILED",
        "UNEXPECTED_UNKNOWN_STATUS",
    ],
)
def test_terminal_or_unknown_outcome_closes_queue(
    chaos_incident,
    monkeypatch,
    orchestration_status,
):
    enqueue_recovery(chaos_incident, max_attempts=3)
    isolate_candidate_discovery(monkeypatch)

    monkeypatch.setattr(
        recovery_worker,
        "recover_incident",
        lambda **kwargs: {
            "incident_id": chaos_incident,
            "recovery_attempt_id": None,
            "orchestration_status": orchestration_status,
            "error": "controlled terminal outcome",
        },
    )

    result = recovery_worker.run_cycle(
        provider=lambda *args, **kwargs: None,
        config=worker_config(),
    )

    current = get_recovery_queue_item(chaos_incident)
    processed = result["processed"][0]

    assert current["state"] == "TERMINAL"
    assert current["last_attempt_status"] == orchestration_status
    assert current["claim_token"] is None
    assert processed["status"] == "TERMINAL"


@pytest.mark.parametrize(
    "orchestration_status",
    [
        "RESOLVED",
        "COMPLETED",
        "ALREADY_RECOVERED",
    ],
)
def test_successful_outcome_completes_queue(
    chaos_incident,
    monkeypatch,
    orchestration_status,
):
    enqueue_recovery(chaos_incident, max_attempts=3)
    isolate_candidate_discovery(monkeypatch)

    monkeypatch.setattr(
        recovery_worker,
        "recover_incident",
        lambda **kwargs: {
            "incident_id": chaos_incident,
            "recovery_attempt_id": None,
            "orchestration_status": orchestration_status,
        },
    )

    result = recovery_worker.run_cycle(
        provider=lambda *args, **kwargs: None,
        config=worker_config(),
    )

    current = get_recovery_queue_item(chaos_incident)
    processed = result["processed"][0]

    assert current["state"] == "COMPLETED"
    assert current["last_attempt_status"] == orchestration_status
    assert current["claim_token"] is None
    assert current["next_attempt_at"] is None
    assert processed["status"] == "COMPLETED"
