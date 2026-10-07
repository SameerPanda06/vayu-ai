import re
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Station
from app.stations import SUPPORTED_STATIONS

# Known aliases mapping to curated station IDs
CURATED_ALIASES = {
    "anand vihar": "anand-vihar",
    "punjabi bagh": "punjabi-bagh",
    "mandir marg": "mandir-marg",
    "igi airport": "igi-airport-t3",
    "t3": "igi-airport-t3",
    "rk puram": "rk-puram",
    "r k puram": "rk-puram",
    "r.k. puram": "rk-puram",
    "sector 62": "noida-sec62",
    "sector-62": "noida-sec62",
    "sec 62": "noida-sec62",
}


def clean_station_name(raw_name: str, city: str = "") -> str:
    """Strip regulatory agency suffixes and repeated city tags."""
    if not raw_name:
        return ""
    # Strip common agency tails like '- DPCC', '- CPCB', '- UPPCB', '- HSPCB', '- IMD'
    cleaned = re.sub(r'[\-,]\s*(?:DPCC|CPCB|UPPCB|HSPCB|IMD|IITD)\b.*$', '', raw_name, flags=re.IGNORECASE).strip()
    # Strip trailing city if present (e.g. 'ITO, Delhi' -> 'ITO')
    if city:
        city_lower = city.strip().lower()
        if cleaned.lower().endswith(f", {city_lower}"):
            cleaned = cleaned[:-len(f", {city_lower}")].strip()
        elif cleaned.lower().endswith(f"- {city_lower}"):
            cleaned = cleaned[:-len(f"- {city_lower}")].strip()
    return cleaned.strip()


def slugify(text: str) -> str:
    """Generate a clean URL/ID friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def resolve_station_id(
    raw_name: str,
    city: str = "Delhi",
    state: str = "Delhi",
) -> Tuple[str, str, float, float]:
    """
    Deterministically match an official station name against curated stations
    or generate a stable slug ID.

    Returns: (station_id, display_name, latitude, longitude)
    """
    cleaned = clean_station_name(raw_name, city=city)
    norm = cleaned.lower()
    norm_collapsed = re.sub(r'[\s_\-]+', ' ', norm)

    # 1. Check curated aliases
    for alias, curated_id in CURATED_ALIASES.items():
        if alias in norm or alias in norm_collapsed:
            curated = SUPPORTED_STATIONS[curated_id]
            return (
                curated.id,
                curated.name,
                curated.latitude,
                curated.longitude,
            )

    # 2. Check direct substring matching on curated names
    for s_id, s_meta in SUPPORTED_STATIONS.items():
        meta_norm = s_meta.name.lower()
        if meta_norm in norm or norm in meta_norm or meta_norm in norm_collapsed:
            return (
                s_meta.id,
                s_meta.name,
                s_meta.latitude,
                s_meta.longitude,
            )

    # 3. New station: generate deterministic slug without duplicate city prefixes
    city_slug = slugify(city) or "delhi"
    name_slug = slugify(cleaned) or "station"

    if name_slug.startswith(f"{city_slug}-") or name_slug == city_slug:
        gen_id = name_slug
    elif name_slug.endswith(f"-{city_slug}"):
        gen_id = name_slug
    else:
        gen_id = f"{city_slug}-{name_slug}"

    gen_id = gen_id[:64]

    # Default coordinates to Delhi geographic center if unspecified
    default_lat = 28.6139
    default_lon = 77.2090

    return (gen_id, cleaned or raw_name, default_lat, default_lon)


def get_or_create_station(
    db: Session,
    raw_name: str,
    city: str,
    state: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Station:
    """
    Ensure the station exists in the database.
    Matches curated stations or inserts a new station row idempotently.
    """
    station_id, display_name, def_lat, def_lon = resolve_station_id(raw_name, city, state)

    # Check if station already exists by primary key
    station = db.query(Station).filter(Station.id == station_id).first()

    lat_final = latitude if (latitude is not None and -90 <= latitude <= 90) else def_lat
    lon_final = longitude if (longitude is not None and -180 <= longitude <= 180) else def_lon

    if station:
        # Update coordinates if previously default and new valid ones arrived
        if (station.latitude == 28.6139 and station.longitude == 77.2090) and (latitude is not None):
            station.latitude = lat_final
            station.longitude = lon_final
        return station

    # Insert new station
    new_station = Station(
        id=station_id,
        name=display_name,
        city=city or "Delhi NCR",
        state=state or "Delhi",
        latitude=lat_final,
        longitude=lon_final,
    )
    db.add(new_station)
    db.flush()  # Flush so foreign keys can reference it in current transaction
    return new_station
