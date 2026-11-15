from fastapi import APIRouter, HTTPException, Path, Query

from incident_service.repository import get_incident, list_incidents
from incident_service.recovery.repository import get_recovery_attempts_for_incident
from api.schemas.recovery import RequeueRequest
from incident_service.recovery.queue_repository import (
    get_recovery_queue_item,
    manual_requeue_recovery,
)


router = APIRouter(
    prefix="/incidents",
    tags=["incidents"],
)


@router.get("")
def get_incidents(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    incidents = list_incidents(limit=limit)
    return {
        "count": len(incidents),
        "items": incidents,
    }


@router.get("/{incident_id}")
def get_incident_by_id(
    incident_id: int = Path(ge=1),
) -> dict:
    incident = get_incident(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found.",
        )

    return incident


@router.get("/{incident_id}/recovery-attempts")
def get_incident_recovery_attempts(
    incident_id: int = Path(ge=1),
) -> dict:
    incident = get_incident(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found.",
        )

    attempts = get_recovery_attempts_for_incident(
        incident_id
    )

    return {
        "incident_id": incident_id,
        "count": len(attempts),
        "items": attempts,
    }


@router.get('/{incident_id}/recovery-queue')
def get_incident_recovery_queue(
    incident_id: int = Path(ge=1),
) -> dict:
    incident = get_incident(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f'Incident {incident_id} not found.',
        )

    queue_item = get_recovery_queue_item(
        incident_id
    )

    if queue_item is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f'Recovery queue item for incident '
                f'{incident_id} not found.'
            ),
        )

    return queue_item


@router.post('/{incident_id}/requeue')
def requeue_incident(
    payload: RequeueRequest,
    incident_id: int = Path(ge=1),
) -> dict:
    incident = get_incident(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f'Incident {incident_id} not found.',
        )

    queue_item = get_recovery_queue_item(incident_id)

    if queue_item is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f'Recovery queue item for incident '
                f'{incident_id} not found.'
            ),
        )

    if queue_item['state'] not in {'EXHAUSTED', 'TERMINAL'}:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Incident {incident_id} recovery queue '
                f'cannot be requeued from state '
                f'{queue_item["state"]}.'
            ),
        )

    requeued = manual_requeue_recovery(
        incident_id=incident_id,
        max_attempts=payload.max_attempts,
    )

    if requeued is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Incident {incident_id} recovery queue '
                f'could not be requeued.'
            ),
        )

    return requeued
