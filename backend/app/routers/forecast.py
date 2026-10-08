from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ExperimentalForecastResponse,
    ForecastResponse,
    ForecastUnits,
)
from app.services.experimental_inference import generate_experimental_forecast
from app.stations import get_all_stations, get_station_by_id
from app.synthetic import REFERENCE_START_TIME, generate_synthetic_forecast

router = APIRouter(tags=["Forecast"])


@router.get("/forecast", response_model=ForecastResponse)
def get_forecast(
    station_id: str = Query(
        ...,
        min_length=1,
        max_length=64,
        description="Supported Delhi NCR station identifier (e.g., 'anand-vihar')",
        examples=["anand-vihar"],
    ),
) -> ForecastResponse:
    """
    Retrieve exactly 72 hourly synthetic forecast records for the specified station.

    Returns deterministic illustrative data coupled with response-level metadata:
    data_mode: "synthetic_demo", generated_at, units, and clear unvalidated disclaimer.
    """
    normalized_id = station_id.strip().lower()
    station = get_station_by_id(normalized_id)

    if not station:
        supported_ids = [s.id for s in get_all_stations()]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "StationNotFound",
                "message": f"Station '{station_id}' is not recognized in Phase 1 demo network.",
                "supported_station_ids": supported_ids,
            },
        )

    forecast_records = generate_synthetic_forecast(station)

    return ForecastResponse(
        data_mode="synthetic_demo",
        statement=(
            "Synthetic demo series for Phase 1 interface and contract validation. "
            "These values are illustrative, deterministic, and unvalidated. "
            "They do NOT represent actual atmospheric observations or certified predictions."
        ),
        generated_at=REFERENCE_START_TIME,
        units=ForecastUnits(),
        station=station,
        forecast_hours=len(forecast_records),
        forecast=forecast_records,
    )


@router.get("/forecast/experimental", response_model=ExperimentalForecastResponse)
def get_experimental_forecast(
    station_id: str = Query(
        ...,
        min_length=1,
        max_length=64,
        description="Supported Delhi NCR station identifier (e.g. 'anand-vihar')",
        examples=["anand-vihar"],
    ),
    reference_time: Optional[datetime] = Query(
        None,
        description=(
            "Optional point-in-time UTC forecast anchor timestamp (ISO-8601). "
            "If omitted, evaluates against current time and enforces real-time freshness."
        ),
        examples=["2024-12-15T12:00:00Z"],
    ),
    max_staleness_hours: int = Query(
        24,
        ge=1,
        le=8760,
        description="Maximum permissible age in hours between current time and latest modeled record (default 24h).",
    ),
    db: Session = Depends(get_db),
) -> ExperimentalForecastResponse:
    """
    Retrieve experimental ML baseline forecasts for +24h, +48h, and +72h PM2.5 concentrations.

    Serves validation-selected baseline models evaluated during Phase 4 Step 2:
    - Point-in-time causal inference with zero future-data lookahead.
    - Model selection derived strictly from lowest validation MAE.
    - Requires continuous 72-hour lag history leading up to the forecast anchor.
    - Rejects stale historical data (>24h) when queried in live mode.
    - Transparent metadata describing model architecture, provenance, and experimental status.

    These predictions are derived from Open-Meteo numerical atmospheric reanalysis models.
    They are NOT official CPCB ground observations and do NOT replace operational forecasts.
    """
    return generate_experimental_forecast(
        db=db,
        station_id=station_id,
        reference_time=reference_time,
        max_staleness_hours=max_staleness_hours,
    )

