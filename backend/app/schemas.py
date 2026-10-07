from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    version: str = Field(..., example="0.1.0")
    app_name: str = Field(..., example="Vayu AI")
    phase: str = Field("Phase 1 Foundation", example="Phase 1 Foundation")
    timestamp_utc: datetime


class Station(BaseModel):
    id: str = Field(..., example="anand-vihar")
    name: str = Field(..., example="Anand Vihar")
    city: str = Field("Delhi NCR", example="Delhi NCR")
    state: str = Field(..., example="Delhi")
    latitude: float = Field(..., example=28.6469)
    longitude: float = Field(..., example=77.3160)
    elevation_m: Optional[float] = Field(None, example=215.0)
    description: str = Field(..., example="Urban transit and commercial junction with high traffic density.")


class StationsResponse(BaseModel):
    count: int = Field(..., example=5)
    stations: List[Station]


class ForecastUnits(BaseModel):
    pm25: str = "µg/m³"
    temperature: str = "°C"
    wind_speed: str = "m/s"
    pbl_height: str = "m"


class HourlyForecastRecord(BaseModel):
    hour_index: int = Field(..., ge=0, le=71, description="Forecast lead hour index from 0 to 71")
    timestamp_utc: datetime = Field(..., description="Valid forecast step timestamp in UTC")
    pm25: float = Field(..., description="PM2.5 concentration in µg/m³ (Not AQI)")
    temperature_c: float = Field(..., description="Ambient temperature in °C")
    wind_speed_ms: float = Field(..., description="Surface wind speed in m/s")
    pbl_height_m: float = Field(..., description="Planetary boundary layer height in metres")


class ForecastResponse(BaseModel):
    data_mode: Literal["synthetic_demo"] = "synthetic_demo"
    statement: str = Field(
        default=(
            "Synthetic demo series for Phase 1 interface and contract validation. "
            "These values are illustrative, deterministic, and unvalidated. "
            "They do NOT represent actual atmospheric observations or certified predictions."
        ),
        description="Disclaimer stating that data is purely illustrative and unvalidated",
    )
    generated_at: datetime = Field(..., description="Generation reference timestamp in UTC")
    units: ForecastUnits = Field(default_factory=ForecastUnits)
    station: Station
    forecast_hours: int = Field(72, description="Total number of hourly steps returned")
    forecast: List[HourlyForecastRecord]
