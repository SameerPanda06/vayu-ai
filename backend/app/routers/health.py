from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings
from app.database import check_database_connection
from app.schemas import DatabaseHealth, HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return backend service operational health, version status, and database state."""
    db_status = check_database_connection()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        app_name=settings.app_name,
        phase="Phase 4 ML Baselines",
        timestamp_utc=datetime.now(timezone.utc),
        database=DatabaseHealth(**db_status),
    )


@router.get("/health/db")
def get_database_health() -> dict:
    """Return dedicated PostgreSQL database connectivity status."""
    return check_database_connection()
