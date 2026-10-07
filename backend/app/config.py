from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vayu AI"
    app_version: str = "0.1.0"
    app_description: str = (
        "Phase 1 Foundation: Air Pollution–Weather Coupled Forecasting System for Delhi NCR"
    )
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    allowed_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
