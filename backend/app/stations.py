from typing import Dict, List, Optional
from app.schemas import Station

SUPPORTED_STATIONS: Dict[str, Station] = {
    "anand-vihar": Station(
        id="anand-vihar",
        name="Anand Vihar",
        city="Delhi NCR",
        state="Delhi",
        latitude=28.6469,
        longitude=77.3160,
        elevation_m=215.0,
        description="East Delhi transport hub with inter-state bus terminal and rail corridor; frequent nocturnal particulate trapping.",
    ),
    "punjabi-bagh": Station(
        id="punjabi-bagh",
        name="Punjabi Bagh",
        city="Delhi NCR",
        state="Delhi",
        latitude=28.6740,
        longitude=77.1310,
        elevation_m=218.0,
        description="West Delhi arterial intersection mixing heavy vehicular flow with dense commercial and residential zones.",
    ),
    "mandir-marg": Station(
        id="mandir-marg",
        name="Mandir Marg",
        city="Delhi NCR",
        state="Delhi",
        latitude=28.6365,
        longitude=77.2011,
        elevation_m=220.0,
        description="Central Delhi urban background station representing central administrative canopy and moderate traffic dispersion.",
    ),
    "igi-airport-t3": Station(
        id="igi-airport-t3",
        name="IGI Airport (T3)",
        city="Delhi NCR",
        state="Delhi",
        latitude=28.5562,
        longitude=77.1000,
        elevation_m=232.0,
        description="South West Delhi airfield environment characterized by open terrain, runway micrometeorology, and advective winds.",
    ),
    "rk-puram": Station(
        id="rk-puram",
        name="R.K. Puram",
        city="Delhi NCR",
        state="Delhi",
        latitude=28.5632,
        longitude=77.1869,
        elevation_m=224.0,
        description="South Delhi institutional and residential basin with localized biomass and traffic micro-sources.",
    ),
    "noida-sec62": Station(
        id="noida-sec62",
        name="Sector 62, Noida",
        city="Delhi NCR",
        state="Uttar Pradesh",
        latitude=28.6245,
        longitude=77.3639,
        elevation_m=208.0,
        description="Eastern NCR institutional and technology corridor bordering industrial belts and highway interchanges.",
    ),
}


def get_all_stations() -> List[Station]:
    return list(SUPPORTED_STATIONS.values())


def get_station_by_id(station_id: str) -> Optional[Station]:
    return SUPPORTED_STATIONS.get(station_id.strip().lower())
