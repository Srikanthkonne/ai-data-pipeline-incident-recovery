from metadata.repository.db import get_connection


def _row_to_dataset(row):
    if row is None:
        return None

    return {
        "id": row[0],
        "namespace": row[1],
        "name": row[2],
        "layer": row[3],
        "owner": row[4],
        "criticality": row[5],
        "sla_minutes": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


def upsert_dataset(
    namespace,
    name,
    layer=None,
    owner=None,
    criticality="MEDIUM",
    sla_minutes=None,
):
    query = """
    INSERT INTO metadata.dataset_registry (
        namespace,
        name,
        layer,
        owner,
        criticality,
        sla_minutes
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (namespace, name)
    DO UPDATE SET
        layer = EXCLUDED.layer,
        owner = EXCLUDED.owner,
        criticality = EXCLUDED.criticality,
        sla_minutes = EXCLUDED.sla_minutes,
        updated_at = CURRENT_TIMESTAMP
    RETURNING
        id,
        namespace,
        name,
        layer,
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
                    layer,
                    owner,
                    criticality,
                    sla_minutes,
                ),
            )
            row = cursor.fetchone()

    return _row_to_dataset(row)


def sync_dataset_technical_metadata(
    namespace,
    name,
    layer=None,
):
    query = """
    INSERT INTO metadata.dataset_registry (
        namespace,
        name,
        layer
    )
    VALUES (%s, %s, %s)
    ON CONFLICT (namespace, name)
    DO UPDATE SET
        layer = EXCLUDED.layer,
        updated_at = CURRENT_TIMESTAMP
    RETURNING
        id,
        namespace,
        name,
        layer,
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
                (namespace, name, layer),
            )
            row = cursor.fetchone()

    return _row_to_dataset(row)


def get_dataset(namespace, name):
    query = """
    SELECT
        id,
        namespace,
        name,
        layer,
        owner,
        criticality,
        sla_minutes,
        created_at,
        updated_at
    FROM metadata.dataset_registry
    WHERE namespace = %s
      AND name = %s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (namespace, name),
            )
            row = cursor.fetchone()

    return _row_to_dataset(row)
