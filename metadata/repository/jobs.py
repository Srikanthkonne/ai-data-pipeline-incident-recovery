from metadata.repository.db import get_connection


def _row_to_job(row):
    if row is None:
        return None

    return {
        "id": row[0],
        "namespace": row[1],
        "name": row[2],
        "job_type": row[3],
        "owner": row[4],
        "criticality": row[5],
        "sla_minutes": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


def upsert_job(
    namespace,
    name,
    job_type=None,
    owner=None,
    criticality="MEDIUM",
    sla_minutes=None,
):
    query = """
    INSERT INTO metadata.job_registry (
        namespace,
        name,
        job_type,
        owner,
        criticality,
        sla_minutes
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (namespace, name)
    DO UPDATE SET
        job_type = EXCLUDED.job_type,
        owner = EXCLUDED.owner,
        criticality = EXCLUDED.criticality,
        sla_minutes = EXCLUDED.sla_minutes,
        updated_at = CURRENT_TIMESTAMP
    RETURNING
        id,
        namespace,
        name,
        job_type,
        owner,
        criticality,
        sla_minutes,
        created_at,
        updated_at;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    namespace,
                    name,
                    job_type,
                    owner,
                    criticality,
                    sla_minutes,
                ),
            )
            row = cursor.fetchone()

    return _row_to_job(row)


def sync_job_technical_metadata(
    namespace,
    name,
    job_type=None,
):
    query = """
    INSERT INTO metadata.job_registry (
        namespace,
        name,
        job_type
    )
    VALUES (%s, %s, %s)
    ON CONFLICT (namespace, name)
    DO UPDATE SET
        job_type = EXCLUDED.job_type,
        updated_at = CURRENT_TIMESTAMP
    RETURNING
        id,
        namespace,
        name,
        job_type,
        owner,
        criticality,
        sla_minutes,
        created_at,
        updated_at;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    namespace,
                    name,
                    job_type,
                ),
            )
            row = cursor.fetchone()

    return _row_to_job(row)


def get_job(namespace, name):
    query = """
    SELECT
        id,
        namespace,
        name,
        job_type,
        owner,
        criticality,
        sla_minutes,
        created_at,
        updated_at
    FROM metadata.job_registry
    WHERE namespace = %s
      AND name = %s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    namespace,
                    name,
                ),
            )
            row = cursor.fetchone()

    return _row_to_job(row)
