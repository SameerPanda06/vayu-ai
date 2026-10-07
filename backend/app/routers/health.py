from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return backend service operational health and version status."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        app_name=settings.app_name,
        phase="Phase 1 Foundation",
        timestamp_utc=datetime.now(timezone.utc),
    )
