from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "incident-recovery-control-plane",
        "phase": "4C",
    }
