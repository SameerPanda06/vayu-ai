from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModeledAirQualityEstimate
from app.schemas import ModeledEstimateItem, ModeledEstimatesResponse, StationsResponse
from app.stations import get_all_stations, get_station_by_id

router = APIRouter(tags=["Stations"])


@router.get("/stations", response_model=StationsResponse)
def list_stations() -> StationsResponse:
    """Return the set of supported Delhi NCR monitoring stations."""
    stations = get_all_stations()
    return StationsResponse(
        count=len(stations),
        stations=stations,
    )


@router.get("/stations/{station_id}/modeled-estimates", response_model=ModeledEstimatesResponse)
def get_station_modeled_estimates(
    station_id: str,
    limit: int = Query(72, ge=1, le=168, description="Maximum hourly records to retrieve"),
    db: Session = Depends(get_db),
) -> ModeledEstimatesResponse:
    """
    Retrieve read-only modeled atmospheric chemistry estimates (Open-Meteo fallback) for a station.
    
    Data Provenance:
    Explicitly tagged with provider='open-meteo' and data_type='modeled_estimate'.
    These values are numerical model outputs and NOT official CPCB station observations.
    """
    normalized_id = station_id.strip().lower()
    station = get_station_by_id(normalized_id)
    if not station:
        supported_ids = [s.id for s in get_all_stations()]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "StationNotFound",
                "message": f"Station '{station_id}' not found in Delhi NCR station catalog.",
                "supported_station_ids": supported_ids,
            },
        )

    db_estimates = (
        db.query(ModeledAirQualityEstimate)
        .filter(ModeledAirQualityEstimate.station_id == normalized_id)
        .order_by(ModeledAirQualityEstimate.valid_time.desc())
        .limit(limit)
        .all()
    )

    items = [
        ModeledEstimateItem(
            valid_time_utc=est.valid_time,
            pm2_5=est.pm2_5,
            pm10=est.pm10,
            no2=est.no2,
            so2=est.so2,
            co=est.co,
            o3=est.o3,
            provider=est.provider,
            model_name=est.model_name,
        )
        for est in reversed(db_estimates)
    ]

    return ModeledEstimatesResponse(
        station_id=normalized_id,
        data_type="modeled_estimate",
        provider="open-meteo",
        statement=(
            "Atmospheric chemistry estimates derived from numerical models (Open-Meteo). "
            "These are NOT official CPCB ground monitoring station observations."
        ),
        count=len(items),
        estimates=items,
    )

