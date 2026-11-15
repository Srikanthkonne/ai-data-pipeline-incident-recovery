#!/usr/bin/env bash
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-ecommerce}"
POSTGRES_USER="${POSTGRES_USER:-dataengineer}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-incident-postgres}"

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"

SQL_FILES=(
  "infrastructure/postgres/init/01_create_source_tables.sql"
  "infrastructure/postgres/init/02_create_incident_tables.sql"
  "infrastructure/postgres/init/02_create_quality_tables.sql"
  "incident_service/recovery/sql/001_create_recovery_attempts.sql"
  "incident_service/recovery/sql/002_prevent_concurrent_recovery.sql"
  "incident_service/recovery/sql/003_add_recovery_lease.sql"
  "incident_service/recovery/sql/004_create_recovery_queue.sql"
  "incident_service/recovery/sql/005_add_recovery_queue_claim_lease.sql"
)

if command -v psql >/dev/null 2>&1; then
  DB_MODE="host"
elif command -v docker >/dev/null 2>&1 \
  && docker inspect -f "{{.State.Running}}" "${POSTGRES_CONTAINER}" 2>/dev/null | grep -q true; then
  DB_MODE="docker"
else
  echo "ERROR: psql is unavailable and ${POSTGRES_CONTAINER} is not running." >&2
  exit 1
fi

echo "Initializing PostgreSQL test schema using ${DB_MODE} mode..."

for sql_file in "${SQL_FILES[@]}"; do
  echo "Applying ${sql_file}"

  if [[ "${DB_MODE}" == "host" ]]; then
    PGPASSWORD="${POSTGRES_PASSWORD}" psql \
      -v ON_ERROR_STOP=1 \
      -h "${POSTGRES_HOST}" \
      -p "${POSTGRES_PORT}" \
      -U "${POSTGRES_USER}" \
      -d "${POSTGRES_DB}" \
      -f "${sql_file}"
  else
    docker exec -i \
      -e PGPASSWORD="${POSTGRES_PASSWORD}" \
      "${POSTGRES_CONTAINER}" \
      psql \
      -v ON_ERROR_STOP=1 \
      -U "${POSTGRES_USER}" \
      -d "${POSTGRES_DB}" \
      < "${sql_file}"
  fi
done

echo "PostgreSQL test schema initialization complete."
