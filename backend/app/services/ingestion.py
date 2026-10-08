from datetime import datetime, timedelta, timezone
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import AirQualityReading, ModeledAirQualityEstimate
from app.services.data_gov_client import (
    DataGovAPIError,
    DataGovAuthError,
    DataGovClient,
)
from app.services.normalization import (
    group_and_normalize_records,
    normalize_open_meteo_estimates,
)
from app.services.open_meteo_client import (
    OpenMeteoClient,
    OpenMeteoError,
)
from app.services.station_matching import get_or_create_station
from app.stations import get_all_stations

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result summary for official CPCB ground observation ingestion."""
    fetched_records: int = 0
    normalized_observations: int = 0
    stations_upserted: int = 0
    readings_inserted: int = 0
    duplicates_skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Fetched records: {self.fetched_records}\n"
            f"Normalized observations: {self.normalized_observations}\n"
            f"Stations inserted/updated: {self.stations_upserted}\n"
            f"Readings inserted: {self.readings_inserted}\n"
            f"Duplicates skipped: {self.duplicates_skipped}"
        )


@dataclass
class ModeledIngestionResult:
    """Result summary for Open-Meteo numerical atmospheric estimates ingestion."""
    records_fetched: int = 0
    normalized_estimates: int = 0
    stations_touched: int = 0
    estimates_inserted: int = 0
    duplicates_skipped: int = 0
    provider: str = "open-meteo"
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Provider: {self.provider}\n"
            f"Fetched records: {self.records_fetched}\n"
            f"Normalized estimates: {self.normalized_estimates}\n"
            f"Stations touched: {self.stations_touched}\n"
            f"Estimates inserted: {self.estimates_inserted}\n"
            f"Duplicates skipped: {self.duplicates_skipped}"
        )


@dataclass
class OrchestratedIngestionResult:
    """Result summary for multi-source ingestion orchestration."""
    selected_mode: str  # "cpcb", "open_meteo", "auto"
    actual_provider: str  # "cpcb" or "open-meteo"
    records_fetched: int = 0
    normalized_count: int = 0
    stations_touched: int = 0
    inserted_rows: int = 0
    duplicates_skipped: int = 0
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Selected source mode: {self.selected_mode}",
            f"Actual provider used: {self.actual_provider}",
            f"API records fetched: {self.records_fetched}",
            f"Normalized observations or estimates: {self.normalized_count}",
            f"Stations touched: {self.stations_touched}",
            f"Inserted rows: {self.inserted_rows}",
            f"Duplicates skipped: {self.duplicates_skipped}",
        ]
        if self.fallback_used:
            lines.append(f"Fallback reason: {self.fallback_reason}")
        if self.errors:
            lines.append(f"Errors: {'; '.join(self.errors)}")
        return "\n".join(lines)


def ingest_air_quality_data(
    db: Session,
    client: Optional[DataGovClient] = None,
    raw_records: Optional[List[Dict[str, Any]]] = None,
    filter_delhi_ncr: bool = True,
) -> IngestionResult:
    """
    Execute end-to-end ingestion of official CPCB air quality data:
    1. Fetch records from data.gov.in (or use supplied raw_records)
    2. Normalize & group into station observations
    3. Match and upsert stations into the stations table
    4. Idempotently insert AirQualityReading records (respecting uq_station_reading_timestamp)
    5. Rollback on failure, commit on success
    """
    result = IngestionResult()

    # Step 1: Fetch raw data if not provided
    if raw_records is not None:
        records = raw_records
    else:
        api_client = client or DataGovClient()
        records = api_client.fetch_records()

    result.fetched_records = len(records)

    # Step 2: Normalize and group records
    observations = group_and_normalize_records(records, filter_delhi_ncr=filter_delhi_ncr)
    result.normalized_observations = len(observations)

    if not observations:
        return result

    # Track distinct station IDs touched in this run
    touched_station_ids = set()

    try:
        # Step 3 & 4: Ingest stations and observations within a managed transaction
        is_postgres = bool(db.bind and db.bind.dialect.name == "postgresql")

        for obs in observations:
            station = get_or_create_station(
                db=db,
                raw_name=obs.station_name,
                city=obs.city,
                state=obs.state,
                latitude=obs.latitude,
                longitude=obs.longitude,
            )
            touched_station_ids.add(station.id)

            if is_postgres:
                # Use atomic PostgreSQL ON CONFLICT DO NOTHING
                stmt = (
                    pg_insert(AirQualityReading)
                    .values(
                        station_id=station.id,
                        timestamp=obs.timestamp,
                        aqi=obs.aqi,
                        pm2_5=obs.pm2_5,
                        pm10=obs.pm10,
                        no2=obs.no2,
                        so2=obs.so2,
                        co=obs.co,
                        o3=obs.o3,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_station_reading_timestamp"
                    )
                )
                exec_res = db.execute(stmt)
                if exec_res.rowcount > 0:
                    result.readings_inserted += 1
                else:
                    result.duplicates_skipped += 1
            else:
                # Portable check-and-insert for non-Postgres test environments
                existing = (
                    db.query(AirQualityReading.id)
                    .filter(
                        AirQualityReading.station_id == station.id,
                        AirQualityReading.timestamp == obs.timestamp,
                    )
                    .first()
                )
                if existing:
                    result.duplicates_skipped += 1
                else:
                    new_reading = AirQualityReading(
                        station_id=station.id,
                        timestamp=obs.timestamp,
                        aqi=obs.aqi,
                        pm2_5=obs.pm2_5,
                        pm10=obs.pm10,
                        no2=obs.no2,
                        so2=obs.so2,
                        co=obs.co,
                        o3=obs.o3,
                    )
                    db.add(new_reading)
                    result.readings_inserted += 1

        db.commit()
        result.stations_upserted = len(touched_station_ids)
        return result

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during AQI data ingestion: {exc}")
        result.errors.append(str(exc))
        raise


def _truncate_to_hour(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def get_latest_completed_hourly_timestamp(ref: Optional[datetime] = None) -> datetime:
    """
    Compute the start timestamp of the latest completed hourly interval.

    In Open-Meteo, hourly timestamps denote the beginning of the interval [t, t+1h).
    An interval is only completed when reference time >= t + 1 hour.
    Therefore, the latest completed interval start timestamp is:
        truncate_to_hour(ref_utc) - 1 hour.
    """
    if ref is None:
        ref = datetime.now(timezone.utc)
    return _truncate_to_hour(ref) - timedelta(hours=1)


def ingest_open_meteo_data(
    db: Session,
    client: Optional[OpenMeteoClient] = None,
    target_stations: Optional[List[Any]] = None,
    past_hours: Optional[int] = None,
    forecast_hours: Optional[int] = None,
    max_timestamp: Optional[datetime] = None,
    exclude_future: bool = True,
    completed_only: bool = True,
) -> ModeledIngestionResult:
    """
    Ingest numerical atmospheric model estimates from Open-Meteo for Delhi NCR stations.
    Maintains strict separation: records are inserted into modeled_air_quality_estimates,
    NEVER into air_quality_readings or forecasts.
    Idempotent: uses uq_modeled_estimate_station_provider_time uniqueness constraint.
    """
    result = ModeledIngestionResult()
    api_client = client or OpenMeteoClient()
    stations = target_stations if target_stations is not None else get_all_stations()

    if not stations:
        return result

    touched_station_ids = set()

    try:
        is_postgres = bool(db.bind and db.bind.dialect.name == "postgresql")

        for station_meta in stations:
            # Ensure the station exists in the stations catalog
            db_station = get_or_create_station(
                db=db,
                raw_name=station_meta.name,
                city=station_meta.city,
                state=station_meta.state,
                latitude=station_meta.latitude,
                longitude=station_meta.longitude,
            )
            touched_station_ids.add(db_station.id)

            # Fetch atmospheric estimates for station coordinates
            raw_payload = api_client.fetch_air_quality(
                latitude=station_meta.latitude,
                longitude=station_meta.longitude,
                past_hours=past_hours,
                forecast_hours=forecast_hours,
            )

            hourly_times = raw_payload.get("hourly", {}).get("time", [])
            result.records_fetched += len(hourly_times)

            # Normalize estimates (including CO µg/m³ to mg/m³ conversion)
            estimates = normalize_open_meteo_estimates(
                station_id=db_station.id,
                payload=raw_payload,
                provider="open-meteo",
            )
            if exclude_future:
                if max_timestamp is not None:
                    effective_cutoff = max_timestamp
                elif completed_only:
                    effective_cutoff = get_latest_completed_hourly_timestamp(datetime.now(timezone.utc))
                else:
                    effective_cutoff = _truncate_to_hour(datetime.now(timezone.utc))
                estimates = [e for e in estimates if e.valid_time <= effective_cutoff]

            result.normalized_estimates += len(estimates)

            for est in estimates:
                if is_postgres:
                    stmt = (
                        pg_insert(ModeledAirQualityEstimate)
                        .values(
                            station_id=est.station_id,
                            valid_time=est.valid_time,
                            pm2_5=est.pm2_5,
                            pm10=est.pm10,
                            no2=est.no2,
                            so2=est.so2,
                            co=est.co,
                            o3=est.o3,
                            provider=est.provider,
                            model_name=est.model_name,
                        )
                        .on_conflict_do_nothing(
                            constraint="uq_modeled_estimate_station_provider_time"
                        )
                    )
                    exec_res = db.execute(stmt)
                    if exec_res.rowcount > 0:
                        result.estimates_inserted += 1
                    else:
                        result.duplicates_skipped += 1
                else:
                    existing = (
                        db.query(ModeledAirQualityEstimate.id)
                        .filter(
                            ModeledAirQualityEstimate.station_id == est.station_id,
                            ModeledAirQualityEstimate.provider == est.provider,
                            ModeledAirQualityEstimate.valid_time == est.valid_time,
                        )
                        .first()
                    )
                    if existing:
                        result.duplicates_skipped += 1
                    else:
                        new_est = ModeledAirQualityEstimate(
                            station_id=est.station_id,
                            valid_time=est.valid_time,
                            pm2_5=est.pm2_5,
                            pm10=est.pm10,
                            no2=est.no2,
                            so2=est.so2,
                            co=est.co,
                            o3=est.o3,
                            provider=est.provider,
                            model_name=est.model_name,
                        )
                        db.add(new_est)
                        result.estimates_inserted += 1

        db.commit()
        result.stations_touched = len(touched_station_ids)
        return result

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during Open-Meteo modeled ingestion: {exc}")
        result.errors.append(str(exc))
        raise


def orchestrate_aqi_ingestion(
    db: Session,
    mode: str = "auto",
    cpcb_client: Optional[DataGovClient] = None,
    open_meteo_client: Optional[OpenMeteoClient] = None,
    cpcb_raw_records: Optional[List[Dict[str, Any]]] = None,
    target_stations: Optional[List[Any]] = None,
) -> OrchestratedIngestionResult:
    """
    Orchestrate air quality data ingestion across supported source modes:
    - "cpcb": CPCB ingestion only. Failure raises without fallback.
    - "open_meteo": Open-Meteo numerical estimates ingestion only.
    - "auto": Attempt CPCB first; fallback to Open-Meteo ONLY on genuine network/upstream failures.
      Does NOT fall back on missing/invalid credentials, invalid config, or coding errors.
    """
    mode_norm = (mode or "auto").strip().lower()
    if mode_norm not in ("cpcb", "open_meteo", "auto"):
        raise ValueError(
            f"Invalid ingestion source mode '{mode}'. Choose from 'cpcb', 'open_meteo', or 'auto'."
        )

    if mode_norm == "open_meteo":
        logger.info("Executing Open-Meteo ingestion only.")
        om_res = ingest_open_meteo_data(
            db=db,
            client=open_meteo_client,
            target_stations=target_stations,
        )
        return OrchestratedIngestionResult(
            selected_mode="open_meteo",
            actual_provider="open-meteo",
            records_fetched=om_res.records_fetched,
            normalized_count=om_res.normalized_estimates,
            stations_touched=om_res.stations_touched,
            inserted_rows=om_res.estimates_inserted,
            duplicates_skipped=om_res.duplicates_skipped,
            errors=om_res.errors,
        )

    if mode_norm == "cpcb":
        logger.info("Executing CPCB ingestion only.")
        cpcb_res = ingest_air_quality_data(
            db=db,
            client=cpcb_client,
            raw_records=cpcb_raw_records,
        )
        return OrchestratedIngestionResult(
            selected_mode="cpcb",
            actual_provider="cpcb",
            records_fetched=cpcb_res.fetched_records,
            normalized_count=cpcb_res.normalized_observations,
            stations_touched=cpcb_res.stations_upserted,
            inserted_rows=cpcb_res.readings_inserted,
            duplicates_skipped=cpcb_res.duplicates_skipped,
            errors=cpcb_res.errors,
        )

    # mode_norm == "auto"
    logger.info("Executing auto ingestion: attempting CPCB primary source first.")
    try:
        cpcb_res = ingest_air_quality_data(
            db=db,
            client=cpcb_client,
            raw_records=cpcb_raw_records,
        )
        logger.info("Primary CPCB ingestion succeeded.")
        return OrchestratedIngestionResult(
            selected_mode="auto",
            actual_provider="cpcb",
            records_fetched=cpcb_res.fetched_records,
            normalized_count=cpcb_res.normalized_observations,
            stations_touched=cpcb_res.stations_upserted,
            inserted_rows=cpcb_res.readings_inserted,
            duplicates_skipped=cpcb_res.duplicates_skipped,
            fallback_used=False,
            errors=cpcb_res.errors,
        )
    except DataGovAuthError:
        # Invalid credentials or missing API key: DO NOT silently fall back!
        logger.error("CPCB authentication or configuration error; not falling back to Open-Meteo.")
        raise
    except (DataGovAPIError, httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        # Genuine network failure, timeout, or upstream HTTP error: activate fallback
        reason = str(exc)
        logger.warning(
            f"CPCB API primary source unreachable ({reason}). "
            f"Activating Open-Meteo development fallback."
        )
        om_res = ingest_open_meteo_data(
            db=db,
            client=open_meteo_client,
            target_stations=target_stations,
        )
        return OrchestratedIngestionResult(
            selected_mode="auto",
            actual_provider="open-meteo",
            records_fetched=om_res.records_fetched,
            normalized_count=om_res.normalized_estimates,
            stations_touched=om_res.stations_touched,
            inserted_rows=om_res.estimates_inserted,
            duplicates_skipped=om_res.duplicates_skipped,
            fallback_used=True,
            fallback_reason=reason,
            errors=om_res.errors,
        )
    except Exception as exc:
        # Programming or database error: DO NOT fall back
        logger.error(f"Unexpected error during CPCB ingestion: {exc}; not falling back.")
        raise


@dataclass
class HistoricalIngestionResult:
    """Result summary for historical numerical atmospheric estimates ingestion."""
    start_date: str
    end_date: str
    records_fetched: int = 0
    normalized_estimates: int = 0
    stations_touched: int = 0
    estimates_inserted: int = 0
    duplicates_skipped: int = 0
    provider: str = "open-meteo"
    station_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Provider: {self.provider}",
            f"Date range: {self.start_date} to {self.end_date}",
            f"Stations processed: {self.stations_touched}",
            f"Total API records fetched: {self.records_fetched}",
            f"Normalized estimates: {self.normalized_estimates}",
            f"Estimates inserted: {self.estimates_inserted}",
            f"Duplicates skipped: {self.duplicates_skipped}",
        ]
        if self.errors:
            lines.append(f"Errors: {'; '.join(self.errors)}")
        return "\n".join(lines)


def ingest_historical_open_meteo_data(
    db: Session,
    start_date: str,
    end_date: str,
    client: Optional[OpenMeteoClient] = None,
    target_stations: Optional[List[Any]] = None,
    max_timestamp: Optional[datetime] = None,
    exclude_future: bool = True,
    completed_only: bool = True,
) -> HistoricalIngestionResult:
    """
    Ingest historical hourly modeled air quality estimates from Open-Meteo for a date window [start_date, end_date].
    Maintains strict provenance separation: all data persists in modeled_air_quality_estimates.
    Idempotent: uses uq_modeled_estimate_station_provider_time constraint.
    """
    from app.services.open_meteo_client import parse_date_string

    start_d = parse_date_string(start_date)
    end_d = parse_date_string(end_date)
    if end_d < start_d:
        raise ValueError(f"end_date ({end_date}) cannot be earlier than start_date ({start_date})")

    result = HistoricalIngestionResult(start_date=start_date, end_date=end_date)
    api_client = client or OpenMeteoClient()
    stations = target_stations if target_stations is not None else get_all_stations()

    if not stations:
        return result

    touched_station_ids = set()

    try:
        is_postgres = bool(db.bind and db.bind.dialect.name == "postgresql")

        for station_meta in stations:
            db_station = get_or_create_station(
                db=db,
                raw_name=station_meta.name,
                city=station_meta.city,
                state=station_meta.state,
                latitude=station_meta.latitude,
                longitude=station_meta.longitude,
            )
            touched_station_ids.add(db_station.id)

            raw_payload = api_client.fetch_historical_air_quality(
                latitude=station_meta.latitude,
                longitude=station_meta.longitude,
                start_date=start_date,
                end_date=end_date,
            )

            hourly_times = raw_payload.get("hourly", {}).get("time", [])
            fetched_count = len(hourly_times)
            result.records_fetched += fetched_count

            estimates = normalize_open_meteo_estimates(
                station_id=db_station.id,
                payload=raw_payload,
                provider="open-meteo",
            )
            if exclude_future:
                if max_timestamp is not None:
                    effective_cutoff = max_timestamp
                elif completed_only:
                    effective_cutoff = get_latest_completed_hourly_timestamp(datetime.now(timezone.utc))
                else:
                    effective_cutoff = _truncate_to_hour(datetime.now(timezone.utc))
                estimates = [e for e in estimates if e.valid_time <= effective_cutoff]

            norm_count = len(estimates)
            result.normalized_estimates += norm_count

            inserted_for_station = 0
            skipped_for_station = 0

            for est in estimates:
                if is_postgres:
                    stmt = (
                        pg_insert(ModeledAirQualityEstimate)
                        .values(
                            station_id=est.station_id,
                            valid_time=est.valid_time,
                            pm2_5=est.pm2_5,
                            pm10=est.pm10,
                            no2=est.no2,
                            so2=est.so2,
                            co=est.co,
                            o3=est.o3,
                            provider=est.provider,
                            model_name=est.model_name,
                        )
                        .on_conflict_do_nothing(
                            constraint="uq_modeled_estimate_station_provider_time"
                        )
                    )
                    exec_res = db.execute(stmt)
                    if exec_res.rowcount > 0:
                        inserted_for_station += 1
                        result.estimates_inserted += 1
                    else:
                        skipped_for_station += 1
                        result.duplicates_skipped += 1
                else:
                    existing = (
                        db.query(ModeledAirQualityEstimate.id)
                        .filter(
                            ModeledAirQualityEstimate.station_id == est.station_id,
                            ModeledAirQualityEstimate.provider == est.provider,
                            ModeledAirQualityEstimate.valid_time == est.valid_time,
                        )
                        .first()
                    )
                    if existing:
                        skipped_for_station += 1
                        result.duplicates_skipped += 1
                    else:
                        new_est = ModeledAirQualityEstimate(
                            station_id=est.station_id,
                            valid_time=est.valid_time,
                            pm2_5=est.pm2_5,
                            pm10=est.pm10,
                            no2=est.no2,
                            so2=est.so2,
                            co=est.co,
                            o3=est.o3,
                            provider=est.provider,
                            model_name=est.model_name,
                        )
                        db.add(new_est)
                        inserted_for_station += 1
                        result.estimates_inserted += 1

            result.station_breakdown[db_station.id] = {
                "fetched": fetched_count,
                "normalized": norm_count,
                "inserted": inserted_for_station,
                "skipped": skipped_for_station,
            }

        db.commit()
        result.stations_touched = len(touched_station_ids)
        return result

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during historical Open-Meteo ingestion: {exc}")
        result.errors.append(str(exc))
        raise

