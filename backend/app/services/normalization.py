import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings

# Indian Standard Time (UTC+05:30) timezone
IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


@dataclass
class NormalizedObservation:
    """Consolidated station observation for a specific timestamp."""
    station_name: str
    city: str
    state: str
    timestamp: datetime  # UTC timezone-aware
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    aqi: Optional[float] = None
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    so2: Optional[float] = None
    co: Optional[float] = None
    o3: Optional[float] = None


def parse_numeric(val: Any) -> Optional[float]:
    """
    Safely convert numeric string or number to float.
    Treats 'NA', 'N/A', empty strings, null, and negative sensor error codes (-999)
    as missing values (None). Does NOT convert invalid values to zero.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        # Sensor error sentinel values such as -999 or -99
        if val < 0 and val in (-999, -99, -9999):
            return None
        return float(val)

    s = str(val).strip()
    if not s or s.upper() in ("NA", "N/A", "NULL", "NONE", "-", "--", "NAN"):
        return None

    try:
        num = float(s)
        if num < 0 and num in (-999, -99, -9999):
            return None
        return num
    except (ValueError, TypeError):
        return None


def parse_observation_timestamp(val: Any) -> Optional[datetime]:
    """
    Parse timestamp string into a timezone-aware UTC datetime.
    Supports formats common in data.gov.in (e.g. '08-10-2026 00:00:00', ISO formats).
    Assumes IST (UTC+05:30) if no timezone offset is explicitly provided.
    """
    if not val:
        return None

    s = str(val).strip()
    if not s or s.upper() in ("NA", "N/A", "NULL"):
        return None

    # Known format patterns
    date_formats = [
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                # CPCB data is recorded in Indian Standard Time (IST)
                dt = dt.replace(tzinfo=IST_TIMEZONE)
            # Normalize to UTC
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    # Fallback to dateutil or isoformat if available
    try:
        from datetime import datetime as dt_cls
        parsed = dt_cls.fromisoformat(s)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST_TIMEZONE)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def standardize_pollutant_name(pollutant_str: Optional[str]) -> Optional[str]:
    """
    Standardize pollutant identifiers into internal field names:
    pm2_5, pm10, no2, so2, co, o3, aqi.
    """
    if not pollutant_str:
        return None

    clean = re.sub(r'[\s_\-\.]+', '', str(pollutant_str).strip().upper())

    if clean in ("PM25", "PM25CONCENTRATION", "PARTICULATE25"):
        return "pm2_5"
    if clean in ("PM10", "PM10CONCENTRATION", "PARTICULATE10"):
        return "pm10"
    if clean in ("NO2", "NITROGENDIOXIDE"):
        return "no2"
    if clean in ("SO2", "SULPHURDIOXIDE", "SULFURDIOXIDE"):
        return "so2"
    if clean in ("CO", "CARBONMONOXIDE"):
        return "co"
    if clean in ("O3", "OZONE"):
        return "o3"
    if clean in ("AQI", "AIRQUALITYINDEX", "INDEX"):
        return "aqi"

    return None


def is_in_delhi_ncr(
    state: str,
    city: str,
    station: str = "",
    allowed_states: Optional[List[str]] = None,
    allowed_cities: Optional[List[str]] = None,
) -> bool:
    """
    Check if a record falls within the configured Delhi NCR geographical scope.
    """
    states = [s.strip().lower() for s in (allowed_states or settings.delhi_ncr_states)]
    cities = [c.strip().lower() for c in (allowed_cities or settings.delhi_ncr_cities)]

    state_norm = (state or "").strip().lower()
    city_norm = (city or "").strip().lower()
    station_norm = (station or "").strip().lower()

    if state_norm in states:
        # If state is Delhi, it's always in scope
        if "delhi" in state_norm:
            return True
        # If in NCR neighboring state, check if city is in NCR cities list
        if any(c in city_norm for c in cities) or any(c in station_norm for c in cities):
            return True

    # Check if city or station explicitly mentions Delhi / NCR cities
    if any(c in city_norm for c in cities) or "delhi" in station_norm:
        return True

    return False


def group_and_normalize_records(
    records: List[Dict[str, Any]],
    filter_delhi_ncr: bool = True,
) -> List[NormalizedObservation]:
    """
    Combine individual pollutant records belonging to the same station and observation timestamp
    into consolidated NormalizedObservation entities.
    """
    grouped: Dict[tuple, NormalizedObservation] = {}

    for rec in records:
        station_name = str(rec.get("station") or rec.get("station_name") or "").strip()
        city = str(rec.get("city") or "").strip()
        state = str(rec.get("state") or "").strip()

        if not station_name:
            continue

        if filter_delhi_ncr and not is_in_delhi_ncr(state, city, station_name):
            continue

        timestamp_raw = rec.get("last_update") or rec.get("timestamp") or rec.get("update_time")
        timestamp_utc = parse_observation_timestamp(timestamp_raw)
        if not timestamp_utc:
            continue

        # Coordinate parsing
        lat = parse_numeric(rec.get("latitude") or rec.get("lat"))
        lon = parse_numeric(rec.get("longitude") or rec.get("long") or rec.get("lon"))

        group_key = (station_name.lower(), timestamp_utc)

        if group_key not in grouped:
            grouped[group_key] = NormalizedObservation(
                station_name=station_name,
                city=city or "Delhi NCR",
                state=state or "Delhi",
                timestamp=timestamp_utc,
                latitude=lat,
                longitude=lon,
            )

        obs = grouped[group_key]

        # Fill coordinates if previously missing
        if obs.latitude is None and lat is not None:
            obs.latitude = lat
        if obs.longitude is None and lon is not None:
            obs.longitude = lon

        # Extract pollutant measurement
        pollutant_id = rec.get("pollutant_id") or rec.get("pollutant")
        standard_pollutant = standardize_pollutant_name(pollutant_id)

        # Pollutant value: prefer pollutant_avg, fallback to pollutant_max / min
        val = parse_numeric(rec.get("pollutant_avg"))
        if val is None:
            val = parse_numeric(rec.get("pollutant_max"))
        if val is None:
            val = parse_numeric(rec.get("pollutant_min"))

        # In some feeds, overall AQI might be in a separate field or pollutant row
        direct_aqi = parse_numeric(rec.get("aqi") or rec.get("index_value"))
        if direct_aqi is not None and obs.aqi is None:
            obs.aqi = direct_aqi

        if standard_pollutant and val is not None:
            if standard_pollutant == "pm2_5" and obs.pm2_5 is None:
                obs.pm2_5 = val
            elif standard_pollutant == "pm10" and obs.pm10 is None:
                obs.pm10 = val
            elif standard_pollutant == "no2" and obs.no2 is None:
                obs.no2 = val
            elif standard_pollutant == "so2" and obs.so2 is None:
                obs.so2 = val
            elif standard_pollutant == "co" and obs.co is None:
                obs.co = val
            elif standard_pollutant == "o3" and obs.o3 is None:
                obs.o3 = val
            elif standard_pollutant == "aqi" and obs.aqi is None:
                obs.aqi = val

    return list(grouped.values())


@dataclass
class NormalizedModeledEstimate:
    """
    Normalized numerical atmospheric model estimate (e.g. Open-Meteo).
    Maintains clean provenance separation from ground-truth CPCB observations.
    """
    station_id: str
    valid_time: datetime  # UTC timezone-aware
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    so2: Optional[float] = None
    co: Optional[float] = None  # Normalized to mg/m³
    o3: Optional[float] = None
    provider: str = "open-meteo"
    model_name: Optional[str] = None


def normalize_open_meteo_estimates(
    station_id: str,
    payload: Dict[str, Any],
    provider: str = "open-meteo",
    model_name: Optional[str] = None,
) -> List[NormalizedModeledEstimate]:
    """
    Transform raw Open-Meteo Air Quality API response into structured NormalizedModeledEstimate records.

    Key guarantees:
    - Parses ISO timestamps explicitly as UTC.
    - Converts Carbon Monoxide from Open-Meteo µg/m³ to standard schema mg/m³: CO_mg_m3 = CO_ug_m3 / 1000.
    - Keeps PM2.5, PM10, NO2, SO2, and O3 in their documented µg/m³ units.
    - Handles null values, missing array sentinels, and mismatched hourly array lengths safely.
    - Never invents missing values or replaces them with zero.
    - Never calculates or assigns an Indian CPCB AQI value.
    """
    if not isinstance(payload, dict):
        return []

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        return []

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        return []

    pm2_5_arr = hourly.get("pm2_5")
    pm10_arr = hourly.get("pm10")
    no2_arr = hourly.get("nitrogen_dioxide")
    so2_arr = hourly.get("sulphur_dioxide")
    co_arr = hourly.get("carbon_monoxide")
    o3_arr = hourly.get("ozone")

    def _extract_val(arr: Any, index: int) -> Optional[float]:
        if not isinstance(arr, list) or index >= len(arr):
            return None
        return parse_numeric(arr[index])

    estimates: List[NormalizedModeledEstimate] = []

    for idx, time_raw in enumerate(times):
        if not time_raw:
            continue

        try:
            time_str = str(time_raw).strip()
            dt = datetime.fromisoformat(time_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        except Exception:
            continue

        pm2_5 = _extract_val(pm2_5_arr, idx)
        pm10 = _extract_val(pm10_arr, idx)
        no2 = _extract_val(no2_arr, idx)
        so2 = _extract_val(so2_arr, idx)
        o3 = _extract_val(o3_arr, idx)

        # Carbon Monoxide: convert µg/m³ to mg/m³
        co_raw_ug = _extract_val(co_arr, idx)
        co_mg = (co_raw_ug / 1000.0) if co_raw_ug is not None else None

        estimates.append(
            NormalizedModeledEstimate(
                station_id=station_id,
                valid_time=dt,
                pm2_5=pm2_5,
                pm10=pm10,
                no2=no2,
                so2=so2,
                co=co_mg,
                o3=o3,
                provider=provider,
                model_name=model_name,
            )
        )

    return estimates

