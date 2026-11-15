from typing import Any


RETRYABLE_OUTCOMES = {
    "RCA_FAILED",
    "EXECUTION_FAILED",
    "VALIDATION_ERROR",
    "VALIDATION_FAILED",
    "LEASE_EXPIRED",
    "RECOVERY_FENCE_REJECTED",
    "RECOVERY_ALREADY_IN_PROGRESS",
    "WORKER_ERROR",
}


TERMINAL_OUTCOMES = {
    "POLICY_FAILED",
    "MANUAL_REVIEW",
    "PRECHECK_ERROR",
    "DRY_RUN",
}


SUCCESS_OUTCOMES = {
    "RESOLVED",
    "COMPLETED",
    "ALREADY_RECOVERED",
}


def classify_recovery_outcome(
    orchestration_status: str,
) -> str:
    """
    Classify one autonomous recovery outcome.

    Returns:
        RETRY
        TERMINAL
        COMPLETED
    """
    status = orchestration_status.strip().upper()

    if status in RETRYABLE_OUTCOMES:
        return "RETRY"

    if status in TERMINAL_OUTCOMES:
        return "TERMINAL"

    if status in SUCCESS_OUTCOMES:
        return "COMPLETED"

    # Unknown outcomes fail closed instead of being
    # retried automatically.
    return "TERMINAL"


def calculate_retry_backoff_seconds(
    autonomous_attempt_count: int,
    *,
    base_seconds: int = 60,
    max_seconds: int = 1800,
) -> int:
    """
    Exponential retry backoff.

    attempt 1 -> base
    attempt 2 -> base * 2
    attempt 3 -> base * 4
    capped at max_seconds.
    """
    if autonomous_attempt_count <= 0:
        raise ValueError(
            "autonomous_attempt_count must be greater than 0."
        )

    if base_seconds <= 0:
        raise ValueError(
            "base_seconds must be greater than 0."
        )

    if max_seconds <= 0:
        raise ValueError(
            "max_seconds must be greater than 0."
        )

    if base_seconds > max_seconds:
        raise ValueError(
            "base_seconds must not exceed max_seconds."
        )

    backoff = (
        base_seconds
        * (2 ** (autonomous_attempt_count - 1))
    )

    return min(backoff, max_seconds)


def get_result_error(
    result: dict[str, Any],
) -> str | None:
    """Extract a useful error string for queue auditing."""
    for key in (
        "error",
        "execution_error",
        "validation_error",
    ):
        value = result.get(key)

        if value:
            return str(value)

    return None
