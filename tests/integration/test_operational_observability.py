from uuid import uuid4

from fastapi.testclient import TestClient

from api.main import app
from incident_service.db import get_db_connection
from incident_service.metrics.repository import get_operational_summary
from incident_service.repository import create_incident
from incident_service.recovery.queue_repository import (
    claim_next_recovery,
    enqueue_recovery,
    schedule_recovery_retry,
)
from incident_service.recovery.repository import (
    create_recovery_attempt,
    update_recovery_attempt,
)


client = TestClient(app)


def create_failure_state():
    test_id = uuid4().hex
    incident = create_incident(
        incident_type="PHASE4E_OBSERVABILITY_TEST",
        dataset_name=f"phase4e.observability.{test_id}",
        source_system="pytest",
        severity="CRITICAL",
        title=f"Phase 4E observability fixture {test_id}",
        description="Temporary metrics integration incident.",
        metadata={
            "automation_eligible": True,
            "phase4e_test": True,
        },
    )
    incident_id = incident["incident_id"]

    attempt = create_recovery_attempt(
        incident_id=incident_id,
        action="PHASE4E_OBSERVABILITY_ACTION",
        status="STARTED",
        automatic_execution_allowed=True,
        lease_seconds=300,
    )
    attempt_id = attempt["recovery_attempt_id"]

    update_recovery_attempt(
        recovery_attempt_id=attempt_id,
        status="EXECUTION_FAILED",
        error_message="controlled observability failure",
    )

    enqueue_recovery(incident_id, max_attempts=3)
    claimed = claim_next_recovery(
        claim_token=f"phase4e-observability-{test_id}",
        claim_seconds=300,
    )
    assert claimed is not None
    assert claimed["incident_id"] == incident_id

    transitioned = schedule_recovery_retry(
        incident_id=incident_id,
        claim_token=claimed["claim_token"],
        recovery_attempt_id=attempt_id,
        attempt_status="EXECUTION_FAILED",
        backoff_seconds=60,
        error_message="controlled observability failure",
    )
    assert transitioned is not None
    assert transitioned["state"] == "RETRY_WAIT"

    return incident_id


def cleanup_incident(incident_id):
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


def test_failure_state_visible_and_cleanup_restores_metrics():
    baseline = get_operational_summary()
    incident_id = create_failure_state()

    try:
        observed = get_operational_summary()

        assert observed["incidents"]["total"] == baseline["incidents"]["total"] + 1
        assert observed["incidents"]["by_status"]["OPEN"] == baseline["incidents"]["by_status"]["OPEN"] + 1

        assert observed["recovery_attempts"]["total"] == baseline["recovery_attempts"]["total"] + 1
        assert observed["recovery_attempts"]["by_status"].get("EXECUTION_FAILED", 0) == baseline["recovery_attempts"]["by_status"].get("EXECUTION_FAILED", 0) + 1

        assert observed["recovery_queue"]["total"] == baseline["recovery_queue"]["total"] + 1
        assert observed["recovery_queue"]["by_state"]["RETRY_WAIT"] == baseline["recovery_queue"]["by_state"]["RETRY_WAIT"] + 1
        assert observed["recovery_queue"]["autonomous_attempts"] == baseline["recovery_queue"]["autonomous_attempts"] + 1
    finally:
        cleanup_incident(incident_id)

    restored = get_operational_summary()
    assert restored["incidents"]["total"] == baseline["incidents"]["total"]
    assert restored["recovery_attempts"]["total"] == baseline["recovery_attempts"]["total"]
    assert restored["recovery_queue"]["total"] == baseline["recovery_queue"]["total"]
    assert restored["recovery_queue"]["by_state"] == baseline["recovery_queue"]["by_state"]
    assert restored["recovery_queue"]["autonomous_attempts"] == baseline["recovery_queue"]["autonomous_attempts"]


def test_json_metrics_endpoint_observes_failure_state():
    baseline = get_operational_summary()
    incident_id = create_failure_state()

    try:
        response = client.get("/metrics/summary")
        assert response.status_code == 200
        payload = response.json()

        assert payload["incidents"]["total"] == baseline["incidents"]["total"] + 1
        assert payload["recovery_attempts"]["by_status"].get("EXECUTION_FAILED", 0) == baseline["recovery_attempts"]["by_status"].get("EXECUTION_FAILED", 0) + 1
        assert payload["recovery_queue"]["by_state"]["RETRY_WAIT"] == baseline["recovery_queue"]["by_state"]["RETRY_WAIT"] + 1
    finally:
        cleanup_incident(incident_id)


def test_prometheus_endpoint_exposes_failure_labels():
    incident_id = create_failure_state()

    try:
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text

        assert "incident_recovery_incidents_by_status" in body
        assert "status=\"OPEN\"" in body
        assert "incident_recovery_recovery_attempts_by_status" in body
        assert "status=\"EXECUTION_FAILED\"" in body
        assert "incident_recovery_queue_items_by_state" in body
        assert "state=\"RETRY_WAIT\"" in body
        assert "incident_recovery_autonomous_attempts" in body
    finally:
        cleanup_incident(incident_id)
