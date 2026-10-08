from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: str = Field(..., description="Connection status: connected, disconnected, or not_configured")
    configured: bool = Field(..., description="Whether DATABASE_URL is configured in environment")
    message: str = Field(..., description="Descriptive status or error message")


class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    version: str = Field(..., example="0.1.0")
    app_name: str = Field(..., example="Vayu AI")
    phase: str = Field("Phase 4 ML Baselines", example="Phase 4 ML Baselines")
    timestamp_utc: datetime
    database: Optional[DatabaseHealth] = Field(
        None,
        description="Database connectivity status",
    )


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


class ModeledEstimateItem(BaseModel):
    valid_time_utc: datetime = Field(..., description="Valid timestamp in UTC")
    pm2_5: Optional[float] = Field(None, description="Modeled PM2.5 concentration in µg/m³")
    pm10: Optional[float] = Field(None, description="Modeled PM10 concentration in µg/m³")
    no2: Optional[float] = Field(None, description="Modeled NO2 concentration in µg/m³")
    so2: Optional[float] = Field(None, description="Modeled SO2 concentration in µg/m³")
    co: Optional[float] = Field(None, description="Modeled CO concentration in mg/m³")
    o3: Optional[float] = Field(None, description="Modeled O3 concentration in µg/m³")
    provider: str = Field("open-meteo", description="Model data provider")
    model_name: Optional[str] = Field(None, description="Atmospheric model identifier")


class ModeledEstimatesResponse(BaseModel):
    station_id: str
    data_type: Literal["modeled_estimate"] = "modeled_estimate"
    provider: str = Field("open-meteo", description="Underlying estimate provider")
    statement: str = Field(
        default=(
            "Atmospheric chemistry estimates derived from numerical models (Open-Meteo). "
            "These are NOT official CPCB ground monitoring station observations."
        ),
        description="Data provenance disclosure",
    )
    count: int
    estimates: List[ModeledEstimateItem]


class ExperimentalHorizonForecast(BaseModel):
    horizon_hours: int = Field(..., description="Forecast horizon in hours: 24, 48, or 72")
    horizon_label: str = Field(..., description="Display label (e.g. '+24h')")
    target_time_utc: datetime = Field(..., description="Target validity timestamp in UTC")
    predicted_pm2_5: float = Field(..., ge=0.0, description="Predicted PM2.5 concentration in µg/m³ (nonnegative)")
    selected_model: str = Field(..., description="Model chosen on validation partition (e.g. 'ridge', 'persistence', 'seasonal_aligned')")
    model_type: str = Field(..., description="Descriptive model architecture and hyperparameters")
    artifact_id: Optional[str] = Field(None, description="Model artifact identifier")
    validation_mae: Optional[float] = Field(None, description="Mean Absolute Error on validation partition during baseline evaluation")


class ExperimentalForecastResponse(BaseModel):
    status: Literal["experimental"] = "experimental"
    is_experimental: bool = Field(True, description="Designates output as unvalidated experimental baseline research")
    station_id: str = Field(..., description="Identifier of the Delhi NCR monitoring station")
    station_name: str = Field(..., description="Human-readable station name")
    prediction_time_utc: datetime = Field(..., description="Point-in-time reference anchor timestamp t_0 in UTC")
    target_pollutant: str = Field("pm2_5", description="Target pollutant forecasted")
    units: str = Field("µg/m³", description="Concentration units")
    forecast_structure: str = Field(
        default="discrete_milestones_24h_48h_72h",
        description="Forecast horizon structure: predicts discrete +24h, +48h, and +72h horizons, not a full 72-point hourly sequence.",
    )
    hourly_sequence_note: str = Field(
        default=(
            "Baseline models predict 3 discrete horizons (+24h, +48h, +72h). "
            "A full 72-step hourly series requires direct 72-head multi-output models or recursive neural autoregression."
        ),
        description="Requirement note for continuous 72-step hourly forecasts",
    )
    data_provider: str = Field(
        default="Open-Meteo (Copernicus CAMS atmospheric composition)",
        description="Atmospheric data provider",
    )
    data_product: str = Field(
        default="CAMS Global Operational Forecast (live inference) & CAMS Global Reanalysis (training)",
        description="Underlying atmospheric modeling products and provenance",
    )
    training_period: dict = Field(
        default_factory=lambda: {
            "start_utc": "2024-10-01T00:00:00Z",
            "end_utc": "2024-12-29T23:00:00Z",
        },
        description="Historical training date range in UTC",
    )
    disclaimer: str = Field(
        default=(
            "Experimental ML baseline forecast derived from Open-Meteo Copernicus CAMS "
            "atmospheric models. These are NOT official CPCB ground observations "
            "and do NOT replace operational forecasts."
        ),
        description="Scientific provenance and experimental disclaimer",
    )
    horizons: List[ExperimentalHorizonForecast] = Field(..., description="Forecasts for +24h, +48h, and +72h")

