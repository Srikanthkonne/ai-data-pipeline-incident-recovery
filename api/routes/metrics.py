from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from incident_service.metrics.prometheus import generate_prometheus_metrics
from incident_service.metrics.repository import get_operational_summary


router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
)


@router.get("")
def get_prometheus_metrics() -> Response:
    return Response(
        content=generate_prometheus_metrics(),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/summary")
def get_metrics_summary() -> dict:
    return get_operational_summary()
