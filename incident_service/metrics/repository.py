from typing import Any

from psycopg2.extras import RealDictCursor

from incident_service.db import get_db_connection


INCIDENT_STATUSES = (
    "OPEN",
    "INVESTIGATING",
    "RECOVERING",
    "RESOLVED",
)

QUEUE_STATES = (
    "READY",
    "PROCESSING",
    "RETRY_WAIT",
    "EXHAUSTED",
    "TERMINAL",
    "COMPLETED",
)


def get_operational_summary() -> dict[str, Any]:
    """Return a read-only operational summary for Phase 4D."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'OPEN') AS open_count,
                    COUNT(*) FILTER (WHERE status = 'INVESTIGATING') AS investigating_count,
                    COUNT(*) FILTER (WHERE status = 'RECOVERING') AS recovering_count,
                    COUNT(*) FILTER (WHERE status = 'RESOLVED') AS resolved_count,
                    AVG(
                        EXTRACT(EPOCH FROM (resolved_at - detected_at))
                    ) FILTER (
                        WHERE status = 'RESOLVED'
                          AND resolved_at IS NOT NULL
                    )::double precision AS mean_time_to_resolution_seconds
                FROM incidents;
                """
            )
            incident_row = dict(cursor.fetchone())

            cursor.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM recovery_attempts
                GROUP BY status
                ORDER BY status;
                """
            )
            attempt_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    state,
                    COUNT(*) AS count,
                    COALESCE(SUM(autonomous_attempt_count), 0) AS autonomous_attempts
                FROM recovery_queue
                GROUP BY state
                ORDER BY state;
                """
            )
            queue_rows = cursor.fetchall()

        incident_by_status = {
            "OPEN": int(incident_row["open_count"]),
            "INVESTIGATING": int(incident_row["investigating_count"]),
            "RECOVERING": int(incident_row["recovering_count"]),
            "RESOLVED": int(incident_row["resolved_count"]),
        }

        attempt_by_status = {
            row["status"]: int(row["count"])
            for row in attempt_rows
        }

        queue_by_state = {state: 0 for state in QUEUE_STATES}
        total_autonomous_attempts = 0
        for row in queue_rows:
            queue_by_state[row["state"]] = int(row["count"])
            total_autonomous_attempts += int(row["autonomous_attempts"])

        mttr = incident_row["mean_time_to_resolution_seconds"]

        total_incidents = int(incident_row["total"])
        resolved_incidents = incident_by_status["RESOLVED"]

        successful_attempts = (
            attempt_by_status.get("COMPLETED", 0)
            + attempt_by_status.get("ALREADY_RECOVERED", 0)
        )
        non_dry_run_attempts = (
            sum(attempt_by_status.values())
            - attempt_by_status.get("DRY_RUN", 0)
        )

        terminal_queue_items = (
            queue_by_state["COMPLETED"]
            + queue_by_state["EXHAUSTED"]
            + queue_by_state["TERMINAL"]
        )
        total_queue_items = sum(queue_by_state.values())

        return {
            "incidents": {
                "total": int(incident_row["total"]),
                "by_status": incident_by_status,
                "mean_time_to_resolution_seconds": (
                    round(float(mttr), 2)
                    if mttr is not None
                    else None
                ),
            },
            "recovery_attempts": {
                "total": sum(attempt_by_status.values()),
                "by_status": attempt_by_status,
            },
            "recovery_queue": {
                "total": total_queue_items,
                "by_state": queue_by_state,
                "autonomous_attempts": total_autonomous_attempts,
            },
            "kpis": {
                "incident_resolution_rate": round(
                    resolved_incidents / total_incidents,
                    4,
                ) if total_incidents else None,
                "recovery_attempt_success_rate": round(
                    successful_attempts / non_dry_run_attempts,
                    4,
                ) if non_dry_run_attempts else None,
                "queue_completion_rate": round(
                    queue_by_state["COMPLETED"] / terminal_queue_items,
                    4,
                ) if terminal_queue_items else None,
                "mean_autonomous_attempts_per_queue_item": round(
                    total_autonomous_attempts / total_queue_items,
                    2,
                ) if total_queue_items else None,
            },
        }
    finally:
        conn.close()
