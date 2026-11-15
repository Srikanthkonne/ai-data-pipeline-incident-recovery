from uuid import uuid4

import pytest

from incident_service.db import get_db_connection
from incident_service.repository import create_incident, get_incident
from incident_service.recovery.executor import RecoveryExecutionError
from incident_service.recovery.repository import get_recovery_attempt
from incident_service.recovery.validator import RecoveryValidationError
import incident_service.recovery.orchestrator as orchestrator


TEST_ACTION = "PHASE4E_TEST_ACTION"


class NoopRecoveryHeartbeat:
    def __init__(self, recovery_attempt_id, **kwargs):
        self.recovery_attempt_id = recovery_attempt_id
        self.last_error = None

    def start(self):
        pass

    def stop(self):
        pass


@pytest.fixture(autouse=True)
def disable_background_heartbeat(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "RecoveryHeartbeat",
        NoopRecoveryHeartbeat,
    )


@pytest.fixture
def chaos_incident():
    test_id = uuid4().hex
    incident = create_incident(
        incident_type="PHASE4E_ORCHESTRATOR_CHAOS_TEST",
        dataset_name=f"phase4e.orchestrator.{test_id}",
        source_system="pytest",
        severity="CRITICAL",
        title=f"Phase 4E orchestrator chaos fixture {test_id}",
        description="Temporary orchestrator failure-injection incident.",
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


def provider(*args, **kwargs):
    return {}


def patch_successful_rca_and_policy(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "investigate_with_ai",
        lambda **kwargs: {
            "assessment": {"summary": "controlled Phase 4E RCA"},
            "rca_facts": {"root_cause": "controlled_test_failure"},
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "choose_recovery_action",
        lambda facts: {
            "action": TEST_ACTION,
            "automatic_execution_allowed": True,
        },
    )


def assert_attempt_status(result, expected_status):
    attempt = get_recovery_attempt(result["recovery_attempt_id"])
    assert attempt is not None
    assert attempt["status"] == expected_status
    return attempt


def test_rca_exception_is_audited_as_rca_failed(
    chaos_incident,
    monkeypatch,
):
    def fail_rca(**kwargs):
        raise RuntimeError("controlled RCA provider failure")

    monkeypatch.setattr(orchestrator, "investigate_with_ai", fail_rca)

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "RCA_FAILED"
    assert "controlled RCA provider failure" in result["error"]
    attempt = assert_attempt_status(result, "RCA_FAILED")
    assert "controlled RCA provider failure" in attempt["error_message"]
    assert get_incident(chaos_incident)["status"] == "OPEN"


def test_policy_exception_is_audited_as_policy_failed(
    chaos_incident,
    monkeypatch,
):
    patch_successful_rca_and_policy(monkeypatch)

    def fail_policy(facts):
        raise RuntimeError("controlled policy failure")

    monkeypatch.setattr(orchestrator, "choose_recovery_action", fail_policy)

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "POLICY_FAILED"
    assert "controlled policy failure" in result["error"]
    assert_attempt_status(result, "POLICY_FAILED")
    assert get_incident(chaos_incident)["status"] == "OPEN"


def test_execution_exception_is_audited_as_execution_failed(
    chaos_incident,
    monkeypatch,
):
    patch_successful_rca_and_policy(monkeypatch)

    monkeypatch.setitem(
        orchestrator.VALIDATORS,
        TEST_ACTION,
        lambda: {"healthy": False, "recovery_needed": True},
    )

    def fail_execution(*args, **kwargs):
        raise RecoveryExecutionError(
            "controlled execution failure",
            details={"failure_type": "PHASE4E_CONTROLLED"},
        )

    monkeypatch.setattr(orchestrator, "execute_recovery_action", fail_execution)

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "EXECUTION_FAILED"
    assert "controlled execution failure" in result["execution_error"]
    attempt = assert_attempt_status(result, "EXECUTION_FAILED")
    assert attempt["execution_result"]["failure_type"] == "PHASE4E_CONTROLLED"
    assert get_incident(chaos_incident)["status"] == "RECOVERING"


def test_validation_exception_is_audited_as_validation_error(
    chaos_incident,
    monkeypatch,
):
    patch_successful_rca_and_policy(monkeypatch)
    calls = {"count": 0}

    def validator():
        calls["count"] += 1
        if calls["count"] == 1:
            return {"healthy": False, "recovery_needed": True}
        raise RecoveryValidationError("controlled validation exception")

    monkeypatch.setitem(orchestrator.VALIDATORS, TEST_ACTION, validator)
    monkeypatch.setattr(
        orchestrator,
        "execute_recovery_action",
        lambda *args, **kwargs: {
            "action": TEST_ACTION,
            "status": "COMPLETED",
            "executed": True,
        },
    )

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "VALIDATION_ERROR"
    assert "controlled validation exception" in result["validation_error"]
    assert_attempt_status(result, "VALIDATION_ERROR")
    assert get_incident(chaos_incident)["status"] == "RECOVERING"


def test_unhealthy_post_execution_validation_is_validation_failed(
    chaos_incident,
    monkeypatch,
):
    patch_successful_rca_and_policy(monkeypatch)

    monkeypatch.setitem(
        orchestrator.VALIDATORS,
        TEST_ACTION,
        lambda: {
            "healthy": False,
            "recovery_needed": True,
            "remaining_detections": ["controlled_failure"],
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "execute_recovery_action",
        lambda *args, **kwargs: {
            "action": TEST_ACTION,
            "status": "COMPLETED",
            "executed": True,
        },
    )

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "VALIDATION_FAILED"
    assert result["validation"]["healthy"] is False
    assert_attempt_status(result, "VALIDATION_FAILED")
    assert get_incident(chaos_incident)["status"] == "RECOVERING"


def test_already_healthy_precheck_skips_execution_and_resolves(
    chaos_incident,
    monkeypatch,
):
    patch_successful_rca_and_policy(monkeypatch)

    monkeypatch.setitem(
        orchestrator.VALIDATORS,
        TEST_ACTION,
        lambda: {"healthy": True, "recovery_needed": False},
    )

    def execution_must_not_run(*args, **kwargs):
        raise AssertionError("execution must be skipped")

    monkeypatch.setattr(
        orchestrator,
        "execute_recovery_action",
        execution_must_not_run,
    )

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "ALREADY_RECOVERED"
    assert result["execution"]["executed"] is False
    assert result["database_status_after"] == "RESOLVED"
    assert_attempt_status(result, "ALREADY_RECOVERED")
    assert get_incident(chaos_incident)["status"] == "RESOLVED"


def test_successful_execution_and_validation_resolves_incident(
    chaos_incident,
    monkeypatch,
):
    patch_successful_rca_and_policy(monkeypatch)
    calls = {"count": 0}

    def validator():
        calls["count"] += 1
        if calls["count"] == 1:
            return {"healthy": False, "recovery_needed": True}
        return {"healthy": True, "recovery_needed": False}

    monkeypatch.setitem(orchestrator.VALIDATORS, TEST_ACTION, validator)
    monkeypatch.setattr(
        orchestrator,
        "execute_recovery_action",
        lambda *args, **kwargs: {
            "action": TEST_ACTION,
            "status": "COMPLETED",
            "executed": True,
        },
    )

    result = orchestrator.recover_incident(
        incident_id=chaos_incident,
        provider=provider,
        dry_run=False,
    )

    assert result["orchestration_status"] == "RESOLVED"
    assert result["database_status_after"] == "RESOLVED"
    assert result["validation"]["healthy"] is True
    attempt = assert_attempt_status(result, "COMPLETED")
    assert attempt["completed_at"] is not None
    assert get_incident(chaos_incident)["status"] == "RESOLVED"
