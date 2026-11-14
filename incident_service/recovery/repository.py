from typing import Any, Optional

from psycopg2.errors import UniqueViolation
from psycopg2.extras import (
    Json,
    RealDictCursor,
)

from incident_service.db import (
    get_db_connection,
)


class RecoveryAlreadyInProgressError(
    RuntimeError
):
    """
    Raised when another active recovery attempt
    already exists for the same incident.
    """

    pass


TERMINAL_RECOVERY_STATUSES = {
    "COMPLETED",
    "EXECUTION_FAILED",
    "VALIDATION_FAILED",
    "VALIDATION_ERROR",
    "MANUAL_REVIEW",
    "DRY_RUN",
    "RCA_FAILED",
    "POLICY_FAILED",
    "LEASE_EXPIRED",
    "ALREADY_RECOVERED",
    "PRECHECK_ERROR",
}


DEFAULT_RECOVERY_LEASE_SECONDS = 300


def _expire_stale_attempts(
    cursor,
    incident_id: int,
) -> None:
    """
    Expire an abandoned active recovery attempt.
    """

    cursor.execute(
        """
        UPDATE recovery_attempts
        SET
            status = 'LEASE_EXPIRED',
            completed_at = CURRENT_TIMESTAMP,
            error_message = COALESCE(
                error_message,
                'Recovery worker lease expired.'
            )
        WHERE incident_id = %s
          AND status IN (
              'STARTED',
              'RECOVERING'
          )
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at <= CURRENT_TIMESTAMP;
        """,
        (incident_id,),
    )


def create_recovery_attempt(
    incident_id: int,
    action: str,
    status: str,
    automatic_execution_allowed: bool,
    rca_assessment: Optional[dict[str, Any]] = None,
    recovery_decision: Optional[dict[str, Any]] = None,
    lease_seconds: int = DEFAULT_RECOVERY_LEASE_SECONDS,
) -> dict[str, Any]:
    """
    Create a recovery attempt with a finite lease.
    """

    if lease_seconds <= 0:
        raise ValueError(
            "lease_seconds must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            _expire_stale_attempts(
                cursor,
                incident_id,
            )

            cursor.execute(
                """
                INSERT INTO recovery_attempts (
                    incident_id,
                    action,
                    status,
                    automatic_execution_allowed,
                    rca_assessment,
                    recovery_decision,
                    heartbeat_at,
                    lease_expires_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                        + (%s * INTERVAL '1 second')
                )
                RETURNING *;
                """,
                (
                    incident_id,
                    action,
                    status.upper(),
                    automatic_execution_allowed,
                    Json(rca_assessment or {}),
                    Json(recovery_decision or {}),
                    lease_seconds,
                ),
            )

            attempt = cursor.fetchone()

        conn.commit()
        return dict(attempt)

    except UniqueViolation as exc:
        conn.rollback()

        if (
            exc.diag.constraint_name
            == "uq_recovery_attempts_active_incident"
        ):
            raise RecoveryAlreadyInProgressError(
                f"Recovery already in progress "
                f"for incident {incident_id}."
            ) from exc

        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_recovery_attempt(
    recovery_attempt_id: int,
) -> Optional[dict[str, Any]]:
    """
    Retrieve one recovery attempt by ID.
    """

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM recovery_attempts
                WHERE recovery_attempt_id = %s;
                """,
                (
                    recovery_attempt_id,
                ),
            )

            attempt = cursor.fetchone()

        return (
            dict(attempt)
            if attempt
            else None
        )

    finally:
        conn.close()


def get_recovery_attempts_for_incident(
    incident_id: int,
) -> list[dict[str, Any]]:
    """
    Retrieve recovery history for one incident.
    """

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM recovery_attempts
                WHERE incident_id = %s
                ORDER BY
                    recovery_attempt_id ASC;
                """,
                (
                    incident_id,
                ),
            )

            attempts = cursor.fetchall()

        return [
            dict(attempt)
            for attempt in attempts
        ]

    finally:
        conn.close()


def update_recovery_attempt(
    recovery_attempt_id: int,
    status: str,
    action: Optional[str] = None,
    automatic_execution_allowed: Optional[
        bool
    ] = None,
    rca_assessment: Optional[
        dict[str, Any]
    ] = None,
    recovery_decision: Optional[
        dict[str, Any]
    ] = None,
    execution_result: Optional[
        dict[str, Any]
    ] = None,
    validation_result: Optional[
        dict[str, Any]
    ] = None,
    error_message: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Update a recovery attempt as orchestration
    progresses.

    The attempt may be created before RCA so the
    concurrency lock is acquired first. RCA,
    recovery-policy, execution, and validation
    details can then be populated incrementally.

    completed_at is populated automatically when
    the attempt enters a terminal state.
    """

    status = status.upper()

    is_terminal = (
        status
        in TERMINAL_RECOVERY_STATUSES
    )

    rca_json = (
        Json(rca_assessment)
        if rca_assessment is not None
        else None
    )

    decision_json = (
        Json(recovery_decision)
        if recovery_decision is not None
        else None
    )

    execution_json = (
        Json(execution_result)
        if execution_result is not None
        else None
    )

    validation_json = (
        Json(validation_result)
        if validation_result is not None
        else None
    )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                UPDATE recovery_attempts
                SET
                    status = %s,

                    action =
                        COALESCE(
                            %s,
                            action
                        ),

                    automatic_execution_allowed =
                        COALESCE(
                            %s,
                            automatic_execution_allowed
                        ),

                    rca_assessment =
                        COALESCE(
                            %s::jsonb,
                            rca_assessment
                        ),

                    recovery_decision =
                        COALESCE(
                            %s::jsonb,
                            recovery_decision
                        ),

                    execution_result =
                        COALESCE(
                            %s::jsonb,
                            execution_result
                        ),

                    validation_result =
                        COALESCE(
                            %s::jsonb,
                            validation_result
                        ),

                    error_message =
                        COALESCE(
                            %s,
                            error_message
                        ),

                    completed_at =
                        CASE
                            WHEN %s
                                THEN CURRENT_TIMESTAMP
                            ELSE completed_at
                        END

                WHERE recovery_attempt_id = %s

                RETURNING *;
                """,
                (
                    status,
                    action,
                    automatic_execution_allowed,
                    rca_json,
                    decision_json,
                    execution_json,
                    validation_json,
                    error_message,
                    is_terminal,
                    recovery_attempt_id,
                ),
            )

            attempt = cursor.fetchone()

        conn.commit()

        return (
            dict(attempt)
            if attempt
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def refresh_recovery_lease(
    recovery_attempt_id: int,
    lease_seconds: int = DEFAULT_RECOVERY_LEASE_SECONDS,
) -> Optional[dict[str, Any]]:
    """
    Refresh the lease for an active recovery worker.
    """

    if lease_seconds <= 0:
        raise ValueError(
            "lease_seconds must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                UPDATE recovery_attempts
                SET
                    heartbeat_at = CURRENT_TIMESTAMP,
                    lease_expires_at =
                        CURRENT_TIMESTAMP
                        + (%s * INTERVAL '1 second')
                WHERE recovery_attempt_id = %s
                  AND status IN (
                      'STARTED',
                      'RECOVERING'
                  )
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at
                      > CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    lease_seconds,
                    recovery_attempt_id,
                ),
            )

            attempt = cursor.fetchone()

        conn.commit()

        return (
            dict(attempt)
            if attempt
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def claim_recovery_execution(
    recovery_attempt_id: int,
    lease_seconds: int = DEFAULT_RECOVERY_LEASE_SECONDS,
) -> Optional[dict[str, Any]]:
    """
    Atomically claim permission to execute recovery.

    The recovery attempt must still own a valid
    STARTED lease. A stale attempt is expired and
    cannot transition into RECOVERING.

    The recovery_attempt_id therefore acts as the
    application-level fencing token.
    """

    if lease_seconds <= 0:
        raise ValueError(
            "lease_seconds must be greater than 0."
        )

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            # If this worker's lease has already
            # expired, make that terminal first.
            cursor.execute(
                """
                UPDATE recovery_attempts
                SET
                    status = 'LEASE_EXPIRED',
                    completed_at =
                        CURRENT_TIMESTAMP,
                    error_message =
                        COALESCE(
                            error_message,
                            'Recovery worker lease '
                            'expired before execution.'
                        )
                WHERE recovery_attempt_id = %s
                  AND status IN (
                      'STARTED',
                      'RECOVERING'
                  )
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at
                      <= CURRENT_TIMESTAMP;
                """,
                (
                    recovery_attempt_id,
                ),
            )

            # Only a still-valid STARTED owner may
            # cross the destructive execution
            # boundary.
            cursor.execute(
                """
                UPDATE recovery_attempts
                SET
                    status = 'RECOVERING',
                    heartbeat_at =
                        CURRENT_TIMESTAMP,
                    lease_expires_at =
                        CURRENT_TIMESTAMP
                        + (
                            %s
                            * INTERVAL '1 second'
                        )
                WHERE recovery_attempt_id = %s
                  AND status = 'STARTED'
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at
                      > CURRENT_TIMESTAMP
                RETURNING *;
                """,
                (
                    lease_seconds,
                    recovery_attempt_id,
                ),
            )

            attempt = cursor.fetchone()

        conn.commit()

        return (
            dict(attempt)
            if attempt
            else None
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
