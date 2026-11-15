from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.incidents import router as incidents_router


app = FastAPI(
    title="AI Data Pipeline Incident Recovery Control Plane",
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(incidents_router)
