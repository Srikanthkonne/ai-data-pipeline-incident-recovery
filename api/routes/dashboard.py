from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["dashboard"])

DASHBOARD_PATH = Path("dashboard/index.html")


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard() -> HTMLResponse:
    return HTMLResponse(
        DASHBOARD_PATH.read_text(encoding="utf-8")
    )
