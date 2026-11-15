import pytest

from incident_service.recovery.retry_policy import (
    calculate_retry_backoff_seconds,
    classify_recovery_outcome,
    get_result_error,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("RCA_FAILED", "RETRY"),
        ("EXECUTION_FAILED", "RETRY"),
        ("VALIDATION_ERROR", "RETRY"),
        ("VALIDATION_FAILED", "RETRY"),
        ("LEASE_EXPIRED", "RETRY"),
        ("RECOVERY_FENCE_REJECTED", "RETRY"),
        ("RECOVERY_ALREADY_IN_PROGRESS", "RETRY"),
        ("WORKER_ERROR", "RETRY"),
    ],
)
def test_retryable_outcomes(status, expected):
    assert classify_recovery_outcome(status) == expected


@pytest.mark.parametrize(
    "status",
    [
        "POLICY_FAILED",
        "MANUAL_REVIEW",
        "PRECHECK_ERROR",
        "DRY_RUN",
    ],
)
def test_terminal_outcomes(status):
    assert classify_recovery_outcome(status) == "TERMINAL"


@pytest.mark.parametrize(
    "status",
    [
        "RESOLVED",
        "COMPLETED",
        "ALREADY_RECOVERED",
    ],
)
def test_success_outcomes(status):
    assert classify_recovery_outcome(status) == "COMPLETED"


def test_unknown_outcome_fails_closed():
    assert classify_recovery_outcome("UNEXPECTED_STATE") == "TERMINAL"


def test_classification_normalizes_case_and_whitespace():
    assert classify_recovery_outcome("  execution_failed  ") == "RETRY"


def test_exponential_backoff():
    assert calculate_retry_backoff_seconds(1) == 60
    assert calculate_retry_backoff_seconds(2) == 120
    assert calculate_retry_backoff_seconds(3) == 240
    assert calculate_retry_backoff_seconds(4) == 480


def test_backoff_is_capped():
    assert calculate_retry_backoff_seconds(
        10,
        base_seconds=60,
        max_seconds=1800,
    ) == 1800


@pytest.mark.parametrize(
    "kwargs",
    [
        {"autonomous_attempt_count": 0},
        {"autonomous_attempt_count": -1},
        {"autonomous_attempt_count": 1, "base_seconds": 0},
        {"autonomous_attempt_count": 1, "max_seconds": 0},
        {
            "autonomous_attempt_count": 1,
            "base_seconds": 120,
            "max_seconds": 60,
        },
    ],
)
def test_invalid_backoff_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        calculate_retry_backoff_seconds(**kwargs)


def test_result_error_priority():
    result = {
        "error": "primary",
        "execution_error": "execution",
        "validation_error": "validation",
    }
    assert get_result_error(result) == "primary"


def test_result_error_fallbacks():
    assert get_result_error({"execution_error": "boom"}) == "boom"
    assert get_result_error({"validation_error": "bad data"}) == "bad data"
    assert get_result_error({}) is None
