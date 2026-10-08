from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.models import AirQualityReading, ModeledAirQualityEstimate
from app.services.dataset_builder import (
    AirQualityDataset,
    build_hourly_dataset,
    ensure_utc,
    truncate_to_hour,
)
from app.stations import SUPPORTED_STATIONS


def test_ensure_utc_and_truncate_to_hour():
    """Verify time normalization helpers enforce timezone-aware UTC and zero minute/second."""
    naive_dt = datetime(2026, 9, 1, 14, 35, 22)
    utc_dt = ensure_utc(naive_dt)
    assert utc_dt.tzinfo == timezone.utc

    truncated = truncate_to_hour(utc_dt)
    assert truncated.minute == 0
    assert truncated.second == 0
    assert truncated.microsecond == 0
    assert truncated.hour == 14


def test_dataset_builder_invalid_inputs():
    """Verify dataset builder validates source and chronological ordering."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("Database not configured.")

    db: Session = session_factory()
    try:
        t_start = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
        t_end = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)

        # 1. Invalid source
        with pytest.raises(ValueError) as exc1:
            build_hourly_dataset(db, "anand-vihar", t_start, t_start, source="invalid_src")
        assert "Invalid source" in str(exc1.value)

        # 2. End before start
        with pytest.raises(ValueError) as exc2:
            build_hourly_dataset(db, "anand-vihar", t_start, t_end, source="open_meteo")
        assert "cannot be earlier than start_time" in str(exc2.value)

    finally:
        db.close()


def test_dataset_builder_chronological_ordering_and_completeness():
    """Verify dataset builder returns strictly sorted chronological records with quality report."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("Database not configured.")

    db: Session = session_factory()
    try:
        start_t = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
        end_t = datetime(2026, 9, 2, 23, 0, tzinfo=timezone.utc)  # 48 hours

        dataset = build_hourly_dataset(
            db=db,
            station_id="anand-vihar",
            start_time=start_t,
            end_time=end_t,
            source="open_meteo",
        )

        assert dataset.station_id == "anand-vihar"
        assert dataset.source == "open_meteo"
        assert dataset.quality_report.total_expected_hours == 48

        # Chronological order assertion
        timestamps = dataset.get_timestamps()
        for i in range(len(timestamps) - 1):
            assert timestamps[i] < timestamps[i + 1]

        # Verify quality report summary formatting
        summary_str = dataset.quality_report.summary()
        assert "=== Dataset Quality Report" in summary_str
        assert "Completeness:" in summary_str

    finally:
        db.close()


def test_dataset_builder_detects_missing_hours():
    """Verify gap detection when records are missing in a date range."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("Database not configured.")

    db: Session = session_factory()
    try:
        # Date window far in the future with 0 records
        start_t = datetime(2030, 1, 1, 0, 0, tzinfo=timezone.utc)
        end_t = datetime(2030, 1, 1, 23, 0, tzinfo=timezone.utc)  # 24 hours

        # Without placeholders
        ds_empty = build_hourly_dataset(
            db=db,
            station_id="anand-vihar",
            start_time=start_t,
            end_time=end_t,
            source="open_meteo",
            include_missing_placeholders=False,
        )
        assert len(ds_empty.records) == 0
        assert ds_empty.quality_report.total_expected_hours == 24
        assert ds_empty.quality_report.available_hours == 0
        assert ds_empty.quality_report.missing_hours == 24
        assert ds_empty.quality_report.completeness_pct == 0.0

        # With placeholders
        ds_placeholders = build_hourly_dataset(
            db=db,
            station_id="anand-vihar",
            start_time=start_t,
            end_time=end_t,
            source="open_meteo",
            include_missing_placeholders=True,
        )
        assert len(ds_placeholders.records) == 24
        assert all(r.is_missing_hour for r in ds_placeholders.records)
        assert all(r.pm2_5 is None for r in ds_placeholders.records)

    finally:
        db.close()


def test_dataset_builder_strict_source_isolation():
    """
    CRITICAL: Verify querying source='cpcb' only inspects air_quality_readings
    and never returns records from modeled_air_quality_estimates.
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("Database not configured.")

    db: Session = session_factory()
    try:
        start_t = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
        end_t = datetime(2026, 9, 7, 23, 0, tzinfo=timezone.utc)

        # Open-Meteo has 168 records for this window
        om_ds = build_hourly_dataset(
            db=db,
            station_id="anand-vihar",
            start_time=start_t,
            end_time=end_t,
            source="open_meteo",
        )
        assert om_ds.quality_report.available_hours == 168

        # CPCB has NO records for this historical window
        cpcb_ds = build_hourly_dataset(
            db=db,
            station_id="anand-vihar",
            start_time=start_t,
            end_time=end_t,
            source="cpcb",
        )
        assert cpcb_ds.quality_report.available_hours == 0
        assert cpcb_ds.quality_report.missing_hours == 168

    finally:
        db.close()
