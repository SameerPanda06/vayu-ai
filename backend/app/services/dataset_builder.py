from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import AirQualityReading, ModeledAirQualityEstimate
from app.stations import get_station_by_id

logger = logging.getLogger(__name__)


@dataclass
class DatasetRecord:
    """A single chronological hourly air quality entry."""
    timestamp: datetime  # UTC timezone-aware
    station_id: str
    source: str          # 'open_meteo' or 'cpcb'
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    so2: Optional[float] = None
    co: Optional[float] = None  # in mg/m³
    o3: Optional[float] = None
    aqi: Optional[float] = None # CPCB only
    is_missing_hour: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "station_id": self.station_id,
            "source": self.source,
            "pm2_5": self.pm2_5,
            "pm10": self.pm10,
            "no2": self.no2,
            "so2": self.so2,
            "co": self.co,
            "o3": self.o3,
            "aqi": self.aqi,
            "is_missing_hour": self.is_missing_hour,
        }


@dataclass
class DatasetQualityReport:
    """Scientific quality, completeness, and provenance diagnostic report for a dataset."""
    station_id: str
    source: str
    start_time: datetime
    end_time: datetime
    total_expected_hours: int
    available_hours: int
    missing_hours: int
    completeness_pct: float
    null_counts: Dict[str, int]
    duplicate_timestamps_found: int = 0
    pollutant_focus: Optional[str] = None
    earliest_recorded: Optional[datetime] = None
    latest_recorded: Optional[datetime] = None

    def summary(self) -> str:
        lines = [
            f"=== Dataset Quality Report: Station '{self.station_id}' ===",
            f"Source / Provider: {self.source}",
            f"Date Range (UTC): {self.start_time.isoformat()} to {self.end_time.isoformat()}",
            f"Total Expected Hours: {self.total_expected_hours}",
            f"Available Hours: {self.available_hours}",
            f"Missing Hours: {self.missing_hours}",
            f"Completeness: {self.completeness_pct:.2f}%",
            f"Duplicate Timestamps Detected: {self.duplicate_timestamps_found}",
            f"Null Counts: {self.null_counts}",
        ]
        if self.earliest_recorded and self.latest_recorded:
            lines.append(
                f"Recorded Span: {self.earliest_recorded.isoformat()} to {self.latest_recorded.isoformat()}"
            )
        lines.append("=========================================================")
        return "\n".join(lines)


@dataclass
class AirQualityDataset:
    """Encapsulates prepared chronological dataset and its metadata validation report."""
    station_id: str
    source: str
    records: List[DatasetRecord]
    quality_report: DatasetQualityReport

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.records]

    def get_values(self, pollutant: str) -> List[Optional[float]]:
        attr = pollutant.lower().replace(".", "_")
        return [getattr(r, attr, None) for r in self.records]

    def get_timestamps(self) -> List[datetime]:
        return [r.timestamp for r in self.records]


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware and converted to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def truncate_to_hour(dt: datetime) -> datetime:
    """Truncate datetime to the start of the hour (minute=0, second=0, microsecond=0)."""
    return dt.replace(minute=0, second=0, microsecond=0)


def build_hourly_dataset(
    db: Session,
    station_id: str,
    start_time: datetime,
    end_time: datetime,
    source: str = "open_meteo",
    pollutant: Optional[str] = None,
    include_missing_placeholders: bool = False,
) -> AirQualityDataset:
    """
    Construct a validated, chronological hourly air quality dataset.

    Key Guarantees:
    - Strict provenance separation: queries 'air_quality_readings' for 'cpcb' or
      'modeled_air_quality_estimates' for 'open_meteo'. Never mixes sources.
    - Chronological ordering: strictly ascending UTC timestamps.
    - Non-imputation policy: missing hours and sensor nulls are preserved as None,
      never silently filled with zeros or interpolated.
    - Rigorous quality report: calculates expected vs available steps, gap statistics,
      and field-level null counts.
    """
    clean_station_id = station_id.strip().lower()
    source_norm = source.strip().lower()

    if source_norm not in ("open_meteo", "cpcb"):
        raise ValueError(f"Invalid source '{source}'. Choose 'open_meteo' or 'cpcb'.")

    # Time normalization
    start_utc = truncate_to_hour(ensure_utc(start_time))
    end_utc = truncate_to_hour(ensure_utc(end_time))

    if end_utc < start_utc:
        raise ValueError(
            f"end_time ({end_utc.isoformat()}) cannot be earlier than start_time ({start_utc.isoformat()})"
        )

    # Compute expected timeline
    delta_hours = int((end_utc - start_utc).total_seconds() // 3600) + 1
    expected_timestamps = [start_utc + timedelta(hours=i) for i in range(delta_hours)]

    # Query database records strictly by chosen source
    raw_records_by_time: Dict[datetime, Any] = {}
    duplicate_count = 0

    if source_norm == "open_meteo":
        db_rows = (
            db.query(ModeledAirQualityEstimate)
            .filter(
                ModeledAirQualityEstimate.station_id == clean_station_id,
                ModeledAirQualityEstimate.valid_time >= start_utc,
                ModeledAirQualityEstimate.valid_time <= end_utc,
            )
            .order_by(ModeledAirQualityEstimate.valid_time.asc())
            .all()
        )
        for row in db_rows:
            t = truncate_to_hour(ensure_utc(row.valid_time))
            if t in raw_records_by_time:
                duplicate_count += 1
            raw_records_by_time[t] = row

    else:  # source_norm == "cpcb"
        db_rows = (
            db.query(AirQualityReading)
            .filter(
                AirQualityReading.station_id == clean_station_id,
                AirQualityReading.timestamp >= start_utc,
                AirQualityReading.timestamp <= end_utc,
            )
            .order_by(AirQualityReading.timestamp.asc())
            .all()
        )
        for row in db_rows:
            t = truncate_to_hour(ensure_utc(row.timestamp))
            if t in raw_records_by_time:
                duplicate_count += 1
            raw_records_by_time[t] = row

    # Build chronological records and audit missing hours / nulls
    dataset_records: List[DatasetRecord] = []
    missing_hours_count = 0
    null_counts: Dict[str, int] = {
        "pm2_5": 0,
        "pm10": 0,
        "no2": 0,
        "so2": 0,
        "co": 0,
        "o3": 0,
    }
    if source_norm == "cpcb":
        null_counts["aqi"] = 0

    earliest_seen: Optional[datetime] = None
    latest_seen: Optional[datetime] = None

    for t in expected_timestamps:
        if t in raw_records_by_time:
            row = raw_records_by_time[t]
            if earliest_seen is None or t < earliest_seen:
                earliest_seen = t
            if latest_seen is None or t > latest_seen:
                latest_seen = t

            pm2_5_val = row.pm2_5
            pm10_val = row.pm10
            no2_val = row.no2
            so2_val = row.so2
            co_val = row.co
            o3_val = row.o3
            aqi_val = getattr(row, "aqi", None)

            if pm2_5_val is None:
                null_counts["pm2_5"] += 1
            if pm10_val is None:
                null_counts["pm10"] += 1
            if no2_val is None:
                null_counts["no2"] += 1
            if so2_val is None:
                null_counts["so2"] += 1
            if co_val is None:
                null_counts["co"] += 1
            if o3_val is None:
                null_counts["o3"] += 1
            if source_norm == "cpcb" and aqi_val is None:
                null_counts["aqi"] += 1

            rec = DatasetRecord(
                timestamp=t,
                station_id=clean_station_id,
                source=source_norm,
                pm2_5=pm2_5_val,
                pm10=pm10_val,
                no2=no2_val,
                so2=so2_val,
                co=co_val,
                o3=o3_val,
                aqi=aqi_val,
                is_missing_hour=False,
            )
            dataset_records.append(rec)
        else:
            missing_hours_count += 1
            if include_missing_placeholders:
                rec = DatasetRecord(
                    timestamp=t,
                    station_id=clean_station_id,
                    source=source_norm,
                    is_missing_hour=True,
                )
                dataset_records.append(rec)

    available_hours = len(raw_records_by_time)
    completeness = round((available_hours / delta_hours) * 100.0, 2) if delta_hours > 0 else 0.0

    report = DatasetQualityReport(
        station_id=clean_station_id,
        source=source_norm,
        start_time=start_utc,
        end_time=end_utc,
        total_expected_hours=delta_hours,
        available_hours=available_hours,
        missing_hours=missing_hours_count,
        completeness_pct=completeness,
        null_counts=null_counts,
        duplicate_timestamps_found=duplicate_count,
        pollutant_focus=pollutant,
        earliest_recorded=earliest_seen,
        latest_recorded=latest_seen,
    )

    return AirQualityDataset(
        station_id=clean_station_id,
        source=source_norm,
        records=dataset_records,
        quality_report=report,
    )
