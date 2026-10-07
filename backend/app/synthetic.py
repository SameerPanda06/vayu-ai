import math
import random
from datetime import datetime, timedelta, timezone
from typing import List

from app.schemas import HourlyForecastRecord, Station

# Constant reference timestamp ensuring complete determinism across test runs and environments
REFERENCE_START_TIME = datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone.utc)
BASE_SEED = 26082  # SIH problem statement SIH26082


def _station_seed(station_id: str) -> int:
    """Generate a deterministic integer seed from the station_id."""
    hash_val = sum((idx + 1) * ord(char) for idx, char in enumerate(station_id))
    return BASE_SEED + hash_val


def generate_synthetic_forecast(station: Station) -> List[HourlyForecastRecord]:
    """
    Generate exactly 72 deterministic hourly synthetic forecast records.

    Physics-inspired diurnal heuristics:
    - Temperature: Min at sunrise (~06:00 IST / 00:30 UTC), max at mid-afternoon (~14:30 IST / 09:00 UTC).
    - PBL Height: Collapses during nocturnal ground inversion (~250-380m), expands up to 1400-1800m during peak solar convective heating.
    - Wind Speed: Calmer during nocturnal inversion (~1.2 - 2.4 m/s), stronger during daytime boundary layer mixing (~3.2 - 5.5 m/s).
    - PM2.5 (µg/m³): Inversely coupled with PBL ventilation and wind, with pronounced morning & evening commuter / biomass peaks (~140 - 240 µg/m³) and afternoon convective dips (~60 - 95 µg/m³).

    NOTE: These values are synthetic, deterministic demonstrations for Phase 1 interface validation.
    They do NOT constitute validated atmospheric predictions.
    """
    station_seed = _station_seed(station.id)
    rng = random.Random(station_seed)

    # Station specific baseline biases
    station_bias_pm25 = {
        "anand-vihar": 32.0,
        "punjabi-bagh": 14.0,
        "mandir-marg": -8.0,
        "igi-airport-t3": -16.0,
        "rk-puram": 8.0,
        "noida-sec62": 18.0,
    }.get(station.id, 0.0)

    station_bias_wind = {
        "igi-airport-t3": 0.8,
        "anand-vihar": -0.4,
    }.get(station.id, 0.0)

    records: List[HourlyForecastRecord] = []

    for hour_idx in range(72):
        step_time = REFERENCE_START_TIME + timedelta(hours=hour_idx)
        # Local Indian Standard Time (UTC + 5:30) hour for diurnal phase
        ist_hour = (step_time.hour + 5.5) % 24.0

        # Deterministic perturbation for this specific hour
        noise_pm = rng.uniform(-4.5, 4.5)
        noise_temp = rng.uniform(-0.6, 0.6)
        noise_wind = rng.uniform(-0.35, 0.35)
        noise_pbl = rng.uniform(-25.0, 25.0)

        # Diurnal temperature curve (peaking ~14:30 IST, min ~05:30 IST)
        # Phase shift: (ist_hour - 14.5) * (2*pi/24) has peak at 14.5
        temp_diurnal = math.cos((ist_hour - 14.5) * (2 * math.pi / 24.0))
        # 17°C min to 31°C max in October transition season
        temp_c = 24.0 + 7.0 * temp_diurnal + noise_temp

        # Diurnal Planetary Boundary Layer (PBL) height
        # Min ~280m at 05:00 IST, Max ~1650m at 14:00 IST
        pbl_diurnal = math.cos((ist_hour - 14.0) * (2 * math.pi / 24.0))
        pbl_m = 960.0 + 680.0 * pbl_diurnal + noise_pbl
        pbl_m = max(220.0, min(1900.0, pbl_m))

        # Wind speed (m/s)
        # Daytime convective wind enhancement
        wind_diurnal = math.cos((ist_hour - 15.0) * (2 * math.pi / 24.0))
        wind_ms = 3.2 + 1.6 * wind_diurnal + station_bias_wind + noise_wind
        wind_ms = max(0.8, min(8.5, wind_ms))

        # PM2.5 concentration (µg/m³)
        # Ventilation factor proxy: PBL * Wind speed
        # Inversion trapping at night + double traffic rush peak (08:30 and 20:30 IST)
        # Morning rush component
        morning_rush = math.exp(-((ist_hour - 8.5) ** 2) / (2 * (1.8 ** 2)))
        # Evening rush / stagnation component
        evening_rush = math.exp(-((ist_hour - 21.0) ** 2) / (2 * (2.2 ** 2)))

        # Ventilation dilution factor (when pbl is high and wind is strong, PM2.5 dilutes)
        ventilation_effect = (1650.0 - pbl_m) / 1650.0 * 65.0

        base_pm25 = 85.0 + station_bias_pm25 + ventilation_effect + 55.0 * morning_rush + 65.0 * evening_rush
        pm25 = max(25.0, base_pm25 + noise_pm)

        records.append(
            HourlyForecastRecord(
                hour_index=hour_idx,
                timestamp_utc=step_time,
                pm25=round(pm25, 1),
                temperature_c=round(temp_c, 1),
                wind_speed_ms=round(wind_ms, 1),
                pbl_height_m=round(pbl_m, 0),
            )
        )

    return records
