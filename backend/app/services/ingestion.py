import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import AirQualityReading
from app.services.data_gov_client import DataGovClient
from app.services.normalization import group_and_normalize_records
from app.services.station_matching import get_or_create_station

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
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
