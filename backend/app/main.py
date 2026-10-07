import sys
from pathlib import Path

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import forecast, health, stations

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure development CORS from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Register API routes under /api
app.include_router(health.router, prefix="/api")
app.include_router(stations.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "phase": "Phase 1 Foundation",
        "notice": "Visit /api/health or /docs for API documentation.",
    }
