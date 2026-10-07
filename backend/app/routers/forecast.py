from fastapi import APIRouter, HTTPException, Query, status
from app.schemas import ForecastResponse, ForecastUnits
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
