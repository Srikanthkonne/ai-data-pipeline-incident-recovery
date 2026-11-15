from uuid import uuid4

import pytest

from incident_service.db import get_db_connection
from incident_service.repository import create_incident
from incident_service.recovery.repository import (
    RecoveryAlreadyInProgressError,
    claim_recovery_execution,
    create_recovery_attempt,
    get_recovery_attempt,
    refresh_recovery_lease,
)


@pytest.fixture
def chaos_incident():
    test_id = uuid4().hex
    incident = create_incident(
        incident_type="PHASE4E_RECOVERY_CHAOS_TEST",
        dataset_name=f"phase4e.recovery.{test_id}",
        source_system="pytest",
        severity="CRITICAL",
        title=f"Phase 4E recovery chaos fixture {test_id}",
        description="Temporary recovery execution integration-test incident.",
        metadata={"phase4e_test": True},
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


def expire_recovery_lease(recovery_attempt_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recovery_attempts
                SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                WHERE recovery_attempt_id = %s;
                """,
                (recovery_attempt_id,),
            )
        conn.commit()
    finally:
        conn.close()


def create_started_attempt(incident_id: int) -> dict:
    return create_recovery_attempt(
        incident_id=incident_id,
        action="PHASE4E_TEST_ACTION",
        status="STARTED",
        automatic_execution_allowed=True,
        lease_seconds=300,
    )


def test_second_active_attempt_is_rejected(chaos_incident):
    first = create_started_attempt(chaos_incident)
    assert first["status"] == "STARTED"

    with pytest.raises(RecoveryAlreadyInProgressError):
        create_started_attempt(chaos_incident)


def test_expired_lease_cannot_be_refreshed(chaos_incident):
    attempt = create_started_attempt(chaos_incident)
    attempt_id = attempt["recovery_attempt_id"]

    expire_recovery_lease(attempt_id)

    refreshed = refresh_recovery_lease(
        recovery_attempt_id=attempt_id,
        lease_seconds=300,
    )
    assert refreshed is None


def test_expired_attempt_cannot_cross_execution_fence(chaos_incident):
    attempt = create_started_attempt(chaos_incident)
    attempt_id = attempt["recovery_attempt_id"]

    expire_recovery_lease(attempt_id)

    claimed = claim_recovery_execution(
        recovery_attempt_id=attempt_id,
        lease_seconds=300,
    )
    assert claimed is None

    persisted = get_recovery_attempt(attempt_id)
    assert persisted["status"] == "LEASE_EXPIRED"
    assert persisted["completed_at"] is not None


def test_old_attempt_is_fenced_after_new_owner_is_created(chaos_incident):
    old_attempt = create_started_attempt(chaos_incident)
    old_id = old_attempt["recovery_attempt_id"]

    expire_recovery_lease(old_id)

    new_attempt = create_started_attempt(chaos_incident)
    new_id = new_attempt["recovery_attempt_id"]

    old_claim = claim_recovery_execution(
        recovery_attempt_id=old_id,
        lease_seconds=300,
    )
    assert old_claim is None

    new_claim = claim_recovery_execution(
        recovery_attempt_id=new_id,
        lease_seconds=300,
    )
    assert new_claim is not None
    assert new_claim["status"] == "RECOVERING"

    persisted_old = get_recovery_attempt(old_id)
    persisted_new = get_recovery_attempt(new_id)

    assert persisted_old["status"] == "LEASE_EXPIRED"
    assert persisted_new["status"] == "RECOVERING"
