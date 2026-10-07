from pathlib import Path
from typing import List, Optional, Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine base directory structure deterministically
# config.py is located at <project_root>/backend/app/config.py
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _get_env_file_candidates() -> Tuple[str, ...]:
    """
    Find .env files deterministically regardless of process working directory.
    Checks project root first, then backend directory, then current working directory.
    """
    candidates = [
        PROJECT_ROOT / ".env",
        BACKEND_DIR / ".env",
        Path.cwd() / ".env",
    ]
    existing = [str(p) for p in candidates if p.is_file()]
    # Fallback to project root path if none exist yet
    return tuple(existing) if existing else (str(PROJECT_ROOT / ".env"),)


class Settings(BaseSettings):
    app_name: str = "Vayu AI"
    app_version: str = "0.1.0"
    app_description: str = (
        "Air Pollution–Weather Coupled Forecasting System for Delhi NCR"
    )
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    allowed_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database configuration (PostgreSQL)
    database_url: Optional[str] = None

    # Official Data.gov.in (CPCB Real-time Air Quality) Configuration
    data_gov_in_api_key: Optional[str] = None
    data_gov_in_resource_id: str = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
    data_gov_in_base_url: str = "https://api.data.gov.in/resource"
    data_gov_in_timeout_seconds: float = 15.0

    # Geographic filter scope: Delhi NCR
    delhi_ncr_states: List[str] = [
        "Delhi",
        "Haryana",
        "Uttar Pradesh",
        "Rajasthan",
    ]
    delhi_ncr_cities: List[str] = [
        "Delhi",
        "New Delhi",
        "Noida",
        "Greater Noida",
        "Ghaziabad",
        "Gurugram",
        "Gurgaon",
        "Faridabad",
        "Ballabgarh",
        "Bhiwadi",
        "Sonipat",
        "Meerut",
    ]

    @property
    def normalized_database_url(self) -> Optional[str]:
        """Normalize standard postgres URLs to use psycopg v3 dialect for SQLAlchemy 2.x."""
        if not self.database_url:
            return None
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://") and not url.startswith("postgresql+"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    model_config = SettingsConfigDict(
        env_file=_get_env_file_candidates(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
