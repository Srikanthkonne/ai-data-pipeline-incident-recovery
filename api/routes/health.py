from fastapi import APIRouter
from fastapi.responses import JSONResponse

from incident_service.db import get_db_connection


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Process-level liveness check."""
    return {
        "status": "healthy",
        "service": "incident-recovery-control-plane",
        "phase": "4C",
    }


@router.get("/ready")
def readiness():
    """Dependency-aware readiness check."""
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        if result != (1,):
            raise RuntimeError(
                "Unexpected PostgreSQL readiness response."
            )

    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "incident-recovery-control-plane",
                "database": "unavailable",
            },
        )

    finally:
        if connection is not None:
            connection.close()

    return {
        "status": "ready",
        "service": "incident-recovery-control-plane",
        "database": "reachable",
    }
