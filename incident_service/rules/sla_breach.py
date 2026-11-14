from typing import Any

from psycopg2.extras import RealDictCursor

from incident_service.db import get_db_connection


def get_sla_monitored_runs() -> list[dict[str, Any]]:
    """
    Return completed pipeline runs for jobs that have
    an SLA configured.
    """
    conn = get_db_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    pr.id AS pipeline_run_id,
                    pr.job_id,
                    pr.run_id,
                    pr.status,
                    pr.started_at,
                    pr.ended_at,
                    pr.duration_ms,
                    jr.namespace,
                    jr.name AS job_name,
                    jr.criticality,
                    jr.sla_minutes
                FROM metadata.pipeline_runs AS pr
                JOIN metadata.job_registry AS jr
                  ON jr.id = pr.job_id
                WHERE jr.sla_minutes IS NOT NULL
                  AND pr.status = 'COMPLETED'
                  AND pr.duration_ms IS NOT NULL
                ORDER BY pr.id;
                """
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    finally:
        conn.close()


def detect_sla_breaches() -> list[dict[str, Any]]:
    """
    Detect completed pipeline runs whose duration exceeded
    the configured SLA.
    """
    runs = get_sla_monitored_runs()

    detections: list[dict[str, Any]] = []

    for run in runs:
        duration_ms = int(
            run["duration_ms"]
        )

        sla_ms = (
            int(run["sla_minutes"])
            * 60_000
        )

        if duration_ms > sla_ms:
            detections.append(
                {
                    "pipeline_run_id": (
                        run["pipeline_run_id"]
                    ),
                    "job_id": run["job_id"],
                    "run_id": run["run_id"],
                    "namespace": run["namespace"],
                    "job_name": run["job_name"],
                    "criticality": (
                        run["criticality"]
                    ),
                    "status": run["status"],
                    "duration_ms": duration_ms,
                    "duration_minutes": (
                        duration_ms / 60_000
                    ),
                    "sla_minutes": (
                        run["sla_minutes"]
                    ),
                    "started_at": (
                        run["started_at"]
                    ),
                    "ended_at": (
                        run["ended_at"]
                    ),
                }
            )

    return detections


def create_sla_breach_incidents() -> list[dict[str, Any]]:
    """
    Detect SLA breaches and persist one incident per breached
    pipeline run.

    Re-running against the same pipeline_run_id will not create
    duplicate incidents.
    """
    from incident_service.repository import (
        create_incident,
        get_incident_by_pipeline_run,
    )

    detections = detect_sla_breaches()

    results = []

    for detection in detections:
        pipeline_run_id = detection[
            "pipeline_run_id"
        ]

        existing_incident = (
            get_incident_by_pipeline_run(
                incident_type="SLA_BREACH",
                pipeline_run_id=pipeline_run_id,
            )
        )

        if existing_incident:
            results.append(
                {
                    "action": "skipped_existing",
                    "incident": existing_incident,
                    "detection": detection,
                }
            )
            continue

        duration_minutes = detection[
            "duration_minutes"
        ]

        sla_minutes = detection[
            "sla_minutes"
        ]

        job_name = detection[
            "job_name"
        ]

        incident = create_incident(
            incident_type="SLA_BREACH",
            dataset_name=job_name,
            source_system="metadata.pipeline_runs",
            severity="HIGH",
            title=(
                "Pipeline SLA breach detected for "
                f"{job_name}"
            ),
            description=(
                f"Pipeline run {detection['run_id']} "
                f"completed in "
                f"{duration_minutes:.2f} minutes, "
                f"exceeding the configured SLA of "
                f"{sla_minutes} minute(s)."
            ),
            metadata={
                "lineage_entity_type": "Job",
                "lineage_namespace": detection["namespace"],
                "lineage_name": job_name,
                "pipeline_run_id": pipeline_run_id,
                "job_id": detection["job_id"],
                "run_id": detection["run_id"],
                "namespace": detection["namespace"],
                "job_name": job_name,
                "criticality": detection[
                    "criticality"
                ],
                "duration_ms": detection[
                    "duration_ms"
                ],
                "duration_minutes": (
                    duration_minutes
                ),
                "sla_minutes": sla_minutes,
                "started_at": (
                    detection["started_at"]
                    .isoformat()
                    if detection["started_at"]
                    else None
                ),
                "ended_at": (
                    detection["ended_at"]
                    .isoformat()
                    if detection["ended_at"]
                    else None
                ),
            },
        )

        results.append(
            {
                "action": "created",
                "incident": incident,
                "detection": detection,
            }
        )

    return results
