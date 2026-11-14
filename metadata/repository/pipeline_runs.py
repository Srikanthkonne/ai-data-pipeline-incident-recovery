from metadata.repository.db import get_connection


def upsert_pipeline_run(
    job_namespace,
    job_name,
    run_id,
    status,
    started_at=None,
    ended_at=None,
    duration_ms=None,
):
    query = """
    INSERT INTO metadata.pipeline_runs (
        job_id,
        run_id,
        status,
        started_at,
        ended_at,
        duration_ms
    )
    SELECT
        id,
        %s,
        %s,
        %s,
        %s,
        %s
    FROM metadata.job_registry
    WHERE namespace = %s
      AND name = %s
    ON CONFLICT (job_id, run_id)
    DO UPDATE SET
        status = EXCLUDED.status,
        started_at = EXCLUDED.started_at,
        ended_at = EXCLUDED.ended_at,
        duration_ms = EXCLUDED.duration_ms
    RETURNING
        id,
        job_id,
        run_id,
        status,
        started_at,
        ended_at,
        duration_ms,
        recorded_at;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    run_id,
                    status,
                    started_at,
                    ended_at,
                    duration_ms,
                    job_namespace,
                    job_name,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            "Cannot persist pipeline run because the job "
            "is not registered in metadata.job_registry."
        )

    return {
        "id": row[0],
        "job_id": row[1],
        "run_id": row[2],
        "status": row[3],
        "started_at": row[4],
        "ended_at": row[5],
        "duration_ms": row[6],
        "recorded_at": row[7],
    }


def get_pipeline_run(
    job_namespace,
    job_name,
    run_id,
):
    query = """
    SELECT
        pr.id,
        pr.job_id,
        pr.run_id,
        pr.status,
        pr.started_at,
        pr.ended_at,
        pr.duration_ms,
        pr.recorded_at
    FROM metadata.pipeline_runs AS pr
    JOIN metadata.job_registry AS jr
      ON jr.id = pr.job_id
    WHERE jr.namespace = %s
      AND jr.name = %s
      AND pr.run_id = %s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    job_namespace,
                    job_name,
                    run_id,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "job_id": row[1],
        "run_id": row[2],
        "status": row[3],
        "started_at": row[4],
        "ended_at": row[5],
        "duration_ms": row[6],
        "recorded_at": row[7],
    }


def get_pipeline_run_by_id(pipeline_run_id):
    """Return one pipeline run using its immutable database primary key."""
    query = """
    SELECT
        pr.id,
        pr.job_id,
        pr.run_id,
        pr.status,
        pr.started_at,
        pr.ended_at,
        pr.duration_ms,
        pr.recorded_at,
        jr.namespace,
        jr.name,
        jr.criticality,
        jr.sla_minutes
    FROM metadata.pipeline_runs AS pr
    JOIN metadata.job_registry AS jr
      ON jr.id = pr.job_id
    WHERE pr.id = %s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (pipeline_run_id,))
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "job_id": row[1],
        "run_id": row[2],
        "status": row[3],
        "started_at": row[4],
        "ended_at": row[5],
        "duration_ms": row[6],
        "recorded_at": row[7],
        "job_namespace": row[8],
        "job_name": row[9],
        "criticality": row[10],
        "sla_minutes": row[11],
    }
