from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from incident_service.db import get_db_connection


DEFAULT_MAX_AUTONOMOUS_ATTEMPTS = 3


def get_recovery_queue_item(
    incident_id: int,
) -> Optional[dict[str, Any]]:
    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM recovery_queue
                WHERE incident_id = %s;
                """,
                (incident_id,),
            )
            item = cursor.fetchone()

        return dict(item) if item else None
    finally:
        conn.close()


def enqueue_recovery(
    incident_id: int,
    max_attempts: int = (
        DEFAULT_MAX_AUTONOMOUS_ATTEMPTS
    ),
) -> dict[str, Any]:
    if max_attempts <= 0:
        raise ValueError(
            "max_attempts must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO recovery_queue (
                    incident_id,
                    state,
                    autonomous_attempt_count,
                    max_attempts,
                    next_attempt_at
                )
                VALUES (
                    %s,
                    'READY',
                    0,
                    %s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (incident_id)
                DO NOTHING
                RETURNING *;
                """,
                (
                    incident_id,
                    max_attempts,
                ),
            )

            item = cursor.fetchone()

            if item is None:
                cursor.execute(
                    """
                    SELECT *
                    FROM recovery_queue
                    WHERE incident_id = %s;
                    """,
                    (incident_id,),
                )
                item = cursor.fetchone()

        conn.commit()
        return dict(item)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def reclaim_expired_claims() -> list[dict[str, Any]]:
    """
    Recover abandoned PROCESSING queue claims.

    An expired claim becomes READY again unless its
    autonomous attempt limit has already been reached.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET
                    state = CASE
                        WHEN autonomous_attempt_count
                            >= max_attempts
                            THEN 'EXHAUSTED'
                        ELSE 'READY'
                    END,
                    next_attempt_at = CASE
                        WHEN autonomous_attempt_count
                            >= max_attempts
                            THEN NULL
                        ELSE CURRENT_TIMESTAMP
                    END,
                    claim_token = NULL,
                    claimed_at = NULL,
                    claim_expires_at = NULL,
                    last_error =
                        'Queue processing claim expired.',
                    updated_at = CURRENT_TIMESTAMP
                WHERE state = 'PROCESSING'
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at
                      <= CURRENT_TIMESTAMP
                RETURNING *;
                """
            )
            items = cursor.fetchall()

        conn.commit()

        return [
            dict(item)
            for item in items
        ]

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def claim_next_recovery(
    claim_token: str,
    claim_seconds: int = 300,
) -> Optional[dict[str, Any]]:
    """
    Atomically claim one due autonomous recovery item.

    FOR UPDATE SKIP LOCKED allows multiple workers to
    compete safely without claiming the same queue row.
    """
    if not claim_token.strip():
        raise ValueError(
            "claim_token must not be empty."
        )

    if claim_seconds <= 0:
        raise ValueError(
            "claim_seconds must be greater than 0."
        )

    reclaim_expired_claims()

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT
                        rq.recovery_queue_id
                    FROM recovery_queue rq
                    JOIN incidents i
                      ON i.incident_id = rq.incident_id
                    WHERE
                        (
                            rq.state = 'READY'
                            OR (
                                rq.state = 'RETRY_WAIT'
                                AND rq.next_attempt_at
                                    <= CURRENT_TIMESTAMP
                            )
                        )
                        AND rq.autonomous_attempt_count
                            < rq.max_attempts
                        AND i.status IN (
                            'OPEN',
                            'INVESTIGATING',
                            'RECOVERING'
                        )
                        AND i.metadata
                            ->> 'automation_eligible'
                            = 'true'
                    ORDER BY
                        CASE i.severity
                            WHEN 'CRITICAL' THEN 1
                            WHEN 'HIGH' THEN 2
                            WHEN 'MEDIUM' THEN 3
                            WHEN 'LOW' THEN 4
                            ELSE 5
                        END,
                        rq.next_attempt_at ASC
                            NULLS FIRST,
                        i.detected_at ASC,
                        i.incident_id ASC
                    FOR UPDATE OF rq SKIP LOCKED
                    LIMIT 1
                )
                UPDATE recovery_queue rq
                SET
                    state = 'PROCESSING',
                    autonomous_attempt_count =
                        rq.autonomous_attempt_count + 1,
                    claim_token = %s,
                    claimed_at = CURRENT_TIMESTAMP,
                    claim_expires_at =
                        CURRENT_TIMESTAMP
                        + (%s * INTERVAL '1 second'),
                    updated_at = CURRENT_TIMESTAMP
                FROM candidate
                WHERE rq.recovery_queue_id =
                    candidate.recovery_queue_id
                RETURNING rq.*;
                """,
                (
                    claim_token,
                    claim_seconds,
                ),
            )

            item = cursor.fetchone()

        conn.commit()

        return (
            dict(item)
            if item
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def refresh_recovery_queue_claim(
    incident_id: int,
    claim_token: str,
    claim_seconds: int = 300,
) -> Optional[dict[str, Any]]:
    """
    Refresh ownership of an active PROCESSING queue item.

    The claim token fences stale workers from extending a
    claim that has already expired or been reassigned.
    """
    if not claim_token.strip():
        raise ValueError(
            "claim_token must not be empty."
        )

    if claim_seconds <= 0:
        raise ValueError(
            "claim_seconds must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET
                    claim_expires_at =
                        CURRENT_TIMESTAMP
                        + (%s * INTERVAL '1 second'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE incident_id = %s
                  AND state = 'PROCESSING'
                  AND claim_token = %s
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at
                      > CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    claim_seconds,
                    incident_id,
                    claim_token,
                ),
            )

            item = cursor.fetchone()

        conn.commit()

        return (
            dict(item)
            if item
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def schedule_recovery_retry(
    incident_id: int,
    claim_token: str,
    recovery_attempt_id: Optional[int],
    attempt_status: str,
    backoff_seconds: int,
    error_message: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Release a claimed queue item into RETRY_WAIT.

    If the current claim already consumed the final
    autonomous attempt, the item becomes EXHAUSTED.
    """
    if not claim_token.strip():
        raise ValueError(
            "claim_token must not be empty."
        )

    if not attempt_status.strip():
        raise ValueError(
            "attempt_status must not be empty."
        )

    if backoff_seconds <= 0:
        raise ValueError(
            "backoff_seconds must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET
                    state = CASE
                        WHEN autonomous_attempt_count
                            >= max_attempts
                            THEN 'EXHAUSTED'
                        ELSE 'RETRY_WAIT'
                    END,
                    next_attempt_at = CASE
                        WHEN autonomous_attempt_count
                            >= max_attempts
                            THEN NULL
                        ELSE CURRENT_TIMESTAMP
                            + (
                                %s
                                * INTERVAL '1 second'
                            )
                    END,
                    last_recovery_attempt_id = %s,
                    last_attempt_status = %s,
                    last_error = %s,
                    claim_token = NULL,
                    claimed_at = NULL,
                    claim_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE incident_id = %s
                  AND state = 'PROCESSING'
                  AND claim_token = %s
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at
                      > CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    backoff_seconds,
                    recovery_attempt_id,
                    attempt_status,
                    error_message,
                    incident_id,
                    claim_token,
                ),
            )

            item = cursor.fetchone()

        conn.commit()

        return (
            dict(item)
            if item
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def _close_recovery_queue_item(
    incident_id: int,
    claim_token: str,
    state: str,
    recovery_attempt_id: Optional[int],
    attempt_status: str,
    error_message: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if state not in {
        'TERMINAL',
        'COMPLETED',
    }:
        raise ValueError(
            "state must be TERMINAL or COMPLETED."
        )

    if not claim_token.strip():
        raise ValueError(
            "claim_token must not be empty."
        )

    if not attempt_status.strip():
        raise ValueError(
            "attempt_status must not be empty."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET
                    state = %s,
                    next_attempt_at = NULL,
                    last_recovery_attempt_id = %s,
                    last_attempt_status = %s,
                    last_error = %s,
                    claim_token = NULL,
                    claimed_at = NULL,
                    claim_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE incident_id = %s
                  AND state = 'PROCESSING'
                  AND claim_token = %s
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at
                      > CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    state,
                    recovery_attempt_id,
                    attempt_status,
                    error_message,
                    incident_id,
                    claim_token,
                ),
            )

            item = cursor.fetchone()

        conn.commit()

        return (
            dict(item)
            if item
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def mark_recovery_queue_terminal(
    incident_id: int,
    claim_token: str,
    recovery_attempt_id: Optional[int],
    attempt_status: str,
    error_message: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    return _close_recovery_queue_item(
        incident_id=incident_id,
        claim_token=claim_token,
        state='TERMINAL',
        recovery_attempt_id=recovery_attempt_id,
        attempt_status=attempt_status,
        error_message=error_message,
    )


def mark_recovery_queue_completed(
    incident_id: int,
    claim_token: str,
    recovery_attempt_id: Optional[int],
    attempt_status: str,
) -> Optional[dict[str, Any]]:
    return _close_recovery_queue_item(
        incident_id=incident_id,
        claim_token=claim_token,
        state='COMPLETED',
        recovery_attempt_id=recovery_attempt_id,
        attempt_status=attempt_status,
    )

def manual_requeue_recovery(
    incident_id: int,
    max_attempts: int = (
        DEFAULT_MAX_AUTONOMOUS_ATTEMPTS
    ),
) -> Optional[dict[str, Any]]:
    """
    Start a new bounded autonomous retry window after
    explicit operator intervention.

    Existing recovery_attempt history is preserved.
    """
    if max_attempts <= 0:
        raise ValueError(
            "max_attempts must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET
                    state = 'READY',
                    autonomous_attempt_count = 0,
                    max_attempts = %s,
                    next_attempt_at = CURRENT_TIMESTAMP,
                    claim_token = NULL,
                    claimed_at = NULL,
                    claim_expires_at = NULL,
                    last_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE incident_id = %s
                  AND state IN (
                      'EXHAUSTED',
                      'TERMINAL'
                  )
                RETURNING *;
                """,
                (
                    max_attempts,
                    incident_id,
                ),
            )

            item = cursor.fetchone()

        conn.commit()

        return (
            dict(item)
            if item
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def release_recovery_queue_claim(
    incident_id: int,
    claim_token: str,
    recovery_attempt_id: Optional[int] = None,
    attempt_status: str = "DRY_RUN",
) -> Optional[dict[str, Any]]:
    """
    Release an owned PROCESSING item back to READY.

    Used for non-consuming operations such as worker dry-run.
    The queue attempt counter is restored because no real
    autonomous recovery attempt was consumed.
    """
    if not claim_token.strip():
        raise ValueError(
            "claim_token must not be empty."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_queue
                SET
                    state = 'READY',
                    autonomous_attempt_count =
                        GREATEST(
                            autonomous_attempt_count - 1,
                            0
                        ),
                    next_attempt_at = CURRENT_TIMESTAMP,
                    last_recovery_attempt_id = %s,
                    last_attempt_status = %s,
                    last_error = NULL,
                    claim_token = NULL,
                    claimed_at = NULL,
                    claim_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE incident_id = %s
                  AND state = 'PROCESSING'
                  AND claim_token = %s
                  AND claim_expires_at IS NOT NULL
                  AND claim_expires_at
                      > CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    recovery_attempt_id,
                    attempt_status,
                    incident_id,
                    claim_token,
                ),
            )

            item = cursor.fetchone()

        conn.commit()

        return dict(item) if item else None

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
