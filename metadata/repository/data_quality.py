from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from metadata.repository.db import get_connection


def get_dq_result_by_id(
    dq_result_id: int,
) -> Optional[dict[str, Any]]:
    """
    Return one persisted data-quality result by its
    immutable primary key.
    """
    query = """
    SELECT
        id,
        dataset_name,
        check_name,
        metric_name,
        metric_value,
        status,
        details,
        run_timestamp
    FROM data_quality_results
    WHERE id = %s;
    """

    with get_connection() as connection:
        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                query,
                (dq_result_id,),
            )

            row = cursor.fetchone()

    return dict(row) if row else None
