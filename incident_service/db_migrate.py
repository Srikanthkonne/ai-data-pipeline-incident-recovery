from pathlib import Path

from incident_service.db import get_db_connection


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MIGRATIONS = [
    "infrastructure/postgres/init/01_create_source_tables.sql",
    "infrastructure/postgres/init/02_create_incident_tables.sql",
    "infrastructure/postgres/init/02_create_quality_tables.sql",
    "metadata/migrations/001_create_metadata_tables.sql",
    "metadata/migrations/002_create_schema_snapshots.sql",
    "incident_service/recovery/sql/001_create_recovery_attempts.sql",
    "incident_service/recovery/sql/002_prevent_concurrent_recovery.sql",
    "incident_service/recovery/sql/003_add_recovery_lease.sql",
    "incident_service/recovery/sql/004_create_recovery_queue.sql",
    "incident_service/recovery/sql/005_add_recovery_queue_claim_lease.sql",
]


def main() -> None:
    connection = get_db_connection()

    try:
        with connection:
            with connection.cursor() as cursor:
                for relative_path in MIGRATIONS:
                    path = PROJECT_ROOT / relative_path
                    print(f"Applying {relative_path}", flush=True)
                    cursor.execute(path.read_text())

        print(
            "PostgreSQL schema initialization complete.",
            flush=True,
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
