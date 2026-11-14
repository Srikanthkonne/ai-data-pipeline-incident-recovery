import hashlib
import json
from typing import Any, Optional

from psycopg2.extras import Json

from metadata.repository.datasets import get_dataset
from metadata.repository.db import get_connection


def calculate_schema_hash(
    schema: dict[str, str],
) -> str:
    """
    Create a deterministic SHA-256 fingerprint for a schema.
    """
    canonical_schema = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical_schema.encode("utf-8")
    ).hexdigest()


def record_schema_snapshot(
    namespace: str,
    name: str,
    schema: dict[str, str],
) -> dict[str, Any]:
    """
    Record an observed dataset schema.

    If the same schema has already been observed for the dataset,
    update last_seen_at and increment observation_count instead of
    creating another snapshot row.
    """
    dataset = get_dataset(
        namespace=namespace,
        name=name,
    )

    if dataset is None:
        raise ValueError(
            f"Dataset is not registered: "
            f"{namespace}/{name}"
        )

    schema_hash = calculate_schema_hash(schema)

    query = """
    INSERT INTO metadata.dataset_schema_snapshots (
        dataset_id,
        schema_hash,
        schema_json
    )
    VALUES (%s, %s, %s)
    ON CONFLICT (dataset_id, schema_hash)
    DO UPDATE SET
        last_seen_at = CURRENT_TIMESTAMP,
        observation_count =
            metadata.dataset_schema_snapshots.observation_count + 1
    RETURNING
        id,
        dataset_id,
        schema_hash,
        schema_json,
        first_seen_at,
        last_seen_at,
        observation_count;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    dataset["id"],
                    schema_hash,
                    Json(schema),
                ),
            )

            row = cursor.fetchone()

    return {
        "id": row[0],
        "dataset_id": row[1],
        "schema_hash": row[2],
        "schema_json": row[3],
        "first_seen_at": row[4],
        "last_seen_at": row[5],
        "observation_count": row[6],
    }


def get_latest_schema_snapshot(
    namespace: str,
    name: str,
) -> Optional[dict[str, Any]]:
    """
    Return the most recently observed schema snapshot for a dataset.
    """
    dataset = get_dataset(
        namespace=namespace,
        name=name,
    )

    if dataset is None:
        return None

    query = """
    SELECT
        id,
        dataset_id,
        schema_hash,
        schema_json,
        first_seen_at,
        last_seen_at,
        observation_count
    FROM metadata.dataset_schema_snapshots
    WHERE dataset_id = %s
    ORDER BY last_seen_at DESC, id DESC
    LIMIT 1;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (dataset["id"],),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "dataset_id": row[1],
        "schema_hash": row[2],
        "schema_json": row[3],
        "first_seen_at": row[4],
        "last_seen_at": row[5],
        "observation_count": row[6],
    }


def get_schema_snapshot_by_id(
    schema_snapshot_id: int,
) -> Optional[dict[str, Any]]:
    """
    Return one schema snapshot using its immutable
    snapshot ID.
    """
    query = """
    SELECT
        id,
        dataset_id,
        schema_hash,
        schema_json,
        first_seen_at,
        last_seen_at,
        observation_count
    FROM metadata.dataset_schema_snapshots
    WHERE id = %s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (schema_snapshot_id,),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "dataset_id": row[1],
        "schema_hash": row[2],
        "schema_json": row[3],
        "first_seen_at": row[4],
        "last_seen_at": row[5],
        "observation_count": row[6],
    }
