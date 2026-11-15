from typing import Any, Optional

from psycopg2.extras import Json, RealDictCursor

from incident_service.db import get_db_connection


def create_incident(
    incident_type: str,
    dataset_name: str,
    source_system: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Create a new incident and return the persisted database record.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                INSERT INTO incidents (
                    incident_type,
                    dataset_name,
                    source_system,
                    severity,
                    title,
                    description,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    incident_type,
                    dataset_name,
                    source_system,
                    severity,
                    title,
                    description,
                    Json(metadata or {}),
                ),
            )

            incident = cursor.fetchone()

        conn.commit()
        return dict(incident)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_incident(incident_id: int) -> Optional[dict[str, Any]]:
    """
    Retrieve a single incident using its incident_id.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM incidents
                WHERE incident_id = %s;
                """,
                (incident_id,),
            )

            incident = cursor.fetchone()

        return dict(incident) if incident else None

    finally:
        conn.close()


ALLOWED_STATUS_TRANSITIONS = {
    "OPEN": {"INVESTIGATING"},
    "INVESTIGATING": {"RECOVERING"},
    "RECOVERING": {"RESOLVED"},
    "RESOLVED": set(),
}


def update_incident_status(
    incident_id: int,
    new_status: str,
) -> Optional[dict[str, Any]]:
    """
    Update an incident through the supported lifecycle.

    Valid lifecycle:
    OPEN -> INVESTIGATING -> RECOVERING -> RESOLVED
    """
    new_status = new_status.upper()

    if new_status not in ALLOWED_STATUS_TRANSITIONS:
        raise ValueError(f"Unsupported incident status: {new_status}")

    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM incidents
                WHERE incident_id = %s
                FOR UPDATE;
                """,
                (incident_id,),
            )

            incident = cursor.fetchone()

            if incident is None:
                conn.rollback()
                return None

            current_status = incident["status"]

            if current_status == new_status:
                conn.commit()
                return dict(incident)

            allowed_next_statuses = ALLOWED_STATUS_TRANSITIONS.get(
                current_status,
                set(),
            )

            if new_status not in allowed_next_statuses:
                raise ValueError(
                    f"Invalid incident status transition: "
                    f"{current_status} -> {new_status}"
                )

            cursor.execute(
                """
                UPDATE incidents
                SET
                    status = %s,
                    resolved_at = CASE
                        WHEN %s = 'RESOLVED'
                            THEN CURRENT_TIMESTAMP
                        ELSE resolved_at
                    END
                WHERE incident_id = %s
                RETURNING *;
                """,
                (
                    new_status,
                    new_status,
                    incident_id,
                ),
            )

            updated_incident = cursor.fetchone()

        conn.commit()
        return dict(updated_incident)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_incident_by_dq_result(
    incident_type: str,
    dq_result_id: int,
) -> Optional[dict[str, Any]]:
    """
    Retrieve an incident created from a specific DQ evidence record.

    This supports idempotent incident creation when detectors are rerun.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM incidents
                WHERE incident_type = %s
                  AND metadata ->> 'dq_result_id' = %s
                ORDER BY incident_id DESC
                LIMIT 1;
                """,
                (
                    incident_type,
                    str(dq_result_id),
                ),
            )

            incident = cursor.fetchone()

        return dict(incident) if incident else None

    finally:
        conn.close()


def get_incident_by_schema_snapshot(
    incident_type: str,
    schema_snapshot_id: int,
) -> Optional[dict[str, Any]]:
    """
    Retrieve an incident created from a specific schema snapshot.

    This makes schema-drift incident creation idempotent when the
    detector runs repeatedly against the same observed schema.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM incidents
                WHERE incident_type = %s
                  AND metadata ->> 'schema_snapshot_id' = %s
                ORDER BY incident_id DESC
                LIMIT 1;
                """,
                (
                    incident_type,
                    str(schema_snapshot_id),
                ),
            )

            incident = cursor.fetchone()

        return (
            dict(incident)
            if incident
            else None
        )

    finally:
        conn.close()


def get_incident_by_pipeline_run(
    incident_type: str,
    pipeline_run_id: int,
) -> Optional[dict[str, Any]]:
    """
    Retrieve an incident created from a specific pipeline run.

    This supports idempotent incident creation when SLA detection
    executes repeatedly against the same run.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM incidents
                WHERE incident_type = %s
                  AND metadata ->> 'pipeline_run_id' = %s
                ORDER BY incident_id DESC
                LIMIT 1;
                """,
                (
                    incident_type,
                    str(pipeline_run_id),
                ),
            )

            incident = cursor.fetchone()

        return (
            dict(incident)
            if incident
            else None
        )

    finally:
        conn.close()


def get_automation_candidates(
    limit: int = 1,
) -> list[dict[str, Any]]:
    """
    Return OPEN incidents explicitly opted in for autonomous processing.

    The metadata flag controls worker eligibility only.
    Recovery authorization remains the responsibility of the
    deterministic recovery policy.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than 0.")

    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM incidents
                WHERE status = 'OPEN'
                  AND metadata ->> 'automation_eligible' = 'true'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM recovery_attempts ra
                      WHERE ra.incident_id = incidents.incident_id
                  )
                ORDER BY
                    CASE severity
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'HIGH' THEN 2
                        WHEN 'MEDIUM' THEN 3
                        WHEN 'LOW' THEN 4
                        ELSE 5
                    END,
                    detected_at ASC,
                    incident_id ASC
                LIMIT %s;
                """,
                (limit,),
            )

            incidents = cursor.fetchall()

        return [
            dict(incident)
            for incident in incidents
        ]

    finally:
        conn.close()
