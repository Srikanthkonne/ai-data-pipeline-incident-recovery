from fastapi.testclient import TestClient

import api.routes.health as health_module
from api.main import app


client = TestClient(app)


def test_health_is_process_liveness():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ready_when_postgres_is_reachable():
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "incident-recovery-control-plane",
        "database": "reachable",
    }


def test_not_ready_when_postgres_is_unavailable(
    monkeypatch,
):
    def fail_connection():
        raise RuntimeError(
            "forced readiness failure"
        )

    monkeypatch.setattr(
        health_module,
        "get_db_connection",
        fail_connection,
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "incident-recovery-control-plane",
        "database": "unavailable",
    }
