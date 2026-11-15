from uuid import uuid4

import pytest

from incident_service.db import get_db_connection
from incident_service.repository import create_incident
from incident_service.recovery.queue_repository import (
    claim_next_recovery,
    enqueue_recovery,
    get_recovery_queue_item,
    manual_requeue_recovery,
    reclaim_expired_claims,
    refresh_recovery_queue_claim,
    schedule_recovery_retry,
)


@pytest.fixture
def chaos_incident():
    test_id = uuid4().hex
    incident = create_incident(
        incident_type="PHASE4E_CHAOS_TEST",
        dataset_name=f"phase4e.{test_id}",
        source_system="pytest",
        severity="CRITICAL",
        title=f"Phase 4E chaos fixture {test_id}",
        description="Temporary integration-test incident.",
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


def expire_claim(incident_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET claim_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                WHERE incident_id = %s;
                """,
                (incident_id,),
            )
        conn.commit()
    finally:
        conn.close()


def test_expired_claim_is_reclaimed(chaos_incident):
    enqueue_recovery(chaos_incident, max_attempts=2)

    claimed = claim_next_recovery(
        claim_token="phase4e-expired-owner",
        claim_seconds=300,
    )

    assert claimed is not None
    assert claimed["incident_id"] == chaos_incident
    assert claimed["state"] == "PROCESSING"
    assert claimed["autonomous_attempt_count"] == 1

    expire_claim(chaos_incident)
    reclaimed = reclaim_expired_claims()

    matching = [
        item for item in reclaimed
        if item["incident_id"] == chaos_incident
    ]
    assert len(matching) == 1
    assert matching[0]["state"] == "READY"
    assert matching[0]["claim_token"] is None
    assert matching[0]["last_error"] == "Queue processing claim expired."


def test_stale_claim_token_is_fenced(chaos_incident):
    enqueue_recovery(chaos_incident, max_attempts=3)

    claimed = claim_next_recovery(
        claim_token="phase4e-current-owner",
        claim_seconds=300,
    )
    assert claimed is not None
    assert claimed["incident_id"] == chaos_incident

    refreshed = refresh_recovery_queue_claim(
        incident_id=chaos_incident,
        claim_token="phase4e-stale-owner",
        claim_seconds=300,
    )
    assert refreshed is None

    transitioned = schedule_recovery_retry(
        incident_id=chaos_incident,
        claim_token="phase4e-stale-owner",
        recovery_attempt_id=None,
        attempt_status="WORKER_ERROR",
        backoff_seconds=1,
        error_message="stale worker must be fenced",
    )
    assert transitioned is None

    current = get_recovery_queue_item(chaos_incident)
    assert current["state"] == "PROCESSING"
    assert current["claim_token"] == "phase4e-current-owner"


def test_second_worker_cannot_claim_owned_item(chaos_incident):
    enqueue_recovery(chaos_incident, max_attempts=3)

    first = claim_next_recovery(
        claim_token="phase4e-worker-a",
        claim_seconds=300,
    )
    assert first is not None
    assert first["incident_id"] == chaos_incident

    second = claim_next_recovery(
        claim_token="phase4e-worker-b",
        claim_seconds=300,
    )
    assert second is None

    current = get_recovery_queue_item(chaos_incident)
    assert current["claim_token"] == "phase4e-worker-a"
    assert current["autonomous_attempt_count"] == 1


def test_retry_exhaustion_and_manual_requeue(chaos_incident):
    enqueue_recovery(chaos_incident, max_attempts=1)

    claimed = claim_next_recovery(
        claim_token="phase4e-exhaust-owner",
        claim_seconds=300,
    )
    assert claimed is not None
    assert claimed["incident_id"] == chaos_incident

    exhausted = schedule_recovery_retry(
        incident_id=chaos_incident,
        claim_token="phase4e-exhaust-owner",
        recovery_attempt_id=None,
        attempt_status="WORKER_ERROR",
        backoff_seconds=1,
        error_message="controlled Phase 4E exhaustion",
    )

    assert exhausted is not None
    assert exhausted["state"] == "EXHAUSTED"
    assert exhausted["autonomous_attempt_count"] == 1
    assert exhausted["max_attempts"] == 1
    assert exhausted["claim_token"] is None

    requeued = manual_requeue_recovery(
        incident_id=chaos_incident,
        max_attempts=2,
    )

    assert requeued is not None
    assert requeued["state"] == "READY"
    assert requeued["autonomous_attempt_count"] == 0
    assert requeued["max_attempts"] == 2
    assert requeued["claim_token"] is None
