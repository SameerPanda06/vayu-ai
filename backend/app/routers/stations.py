from fastapi import APIRouter
from app.schemas import StationsResponse
from app.stations import get_all_stations

router = APIRouter(tags=["Stations"])


@router.get("/stations", response_model=StationsResponse)
def list_stations() -> StationsResponse:
    """Return the set of supported Delhi NCR monitoring stations."""
    stations = get_all_stations()
    return StationsResponse(
        count=len(stations),
        stations=stations,
    )
