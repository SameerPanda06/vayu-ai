from datetime import date, datetime, timezone
from typing import Any, Dict, List
import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.models import AirQualityReading, ModeledAirQualityEstimate
from app.services.ingestion import ingest_historical_open_meteo_data
from app.services.open_meteo_client import (
    OpenMeteoClient,
    OpenMeteoError,
    OpenMeteoNetworkError,
    OpenMeteoRateLimitError,
    OpenMeteoResponseError,
    OpenMeteoTimeoutError,
    parse_date_string,
)
from app.stations import SUPPORTED_STATIONS


# -----------------------------------------------------------------------------
# 1. Date Validation Tests
# -----------------------------------------------------------------------------

def test_parse_date_string_valid():
    """Verify parse_date_string correctly converts YYYY-MM-DD strings to date objects."""
    d = parse_date_string("2026-09-01")
    assert d == date(2026, 9, 1)
    assert d.year == 2026
    assert d.month == 9
    assert d.day == 1


def test_parse_date_string_invalid():
    """Verify parse_date_string raises ValueError on invalid formats."""
    with pytest.raises(ValueError) as exc:
        parse_date_string("01-09-2026")
    assert "Expected 'YYYY-MM-DD'" in str(exc.value)

    with pytest.raises(ValueError):
        parse_date_string("invalid-date")

    with pytest.raises(ValueError):
        parse_date_string("")


def test_historical_date_range_ordering():
    """Verify that end_date prior to start_date raises ValueError."""
    client = OpenMeteoClient()
    with pytest.raises(ValueError) as exc:
        client.fetch_historical_air_quality(
            latitude=28.6469,
            longitude=77.3160,
            start_date="2026-09-10",
            end_date="2026-09-01",
        )
    assert "cannot be earlier than start_date" in str(exc.value)


# -----------------------------------------------------------------------------
# 2. Historical API Client & Retry / Chunking Tests
# -----------------------------------------------------------------------------

def test_historical_api_params_construction(monkeypatch):
    """Verify fetch_historical_air_quality constructs correct query parameters."""
    captured_params = {}

    def mock_get(self, url, params=None, **kwargs):
        nonlocal captured_params
        captured_params = params
        return httpx.Response(
            status_code=200,
            json={
                "hourly": {
                    "time": ["2026-09-01T00:00"],
                    "pm2_5": [55.0],
                }
            },
        )

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    client = OpenMeteoClient()
    client.fetch_historical_air_quality(
        latitude=28.6469,
        longitude=77.3160,
        start_date="2026-09-01",
        end_date="2026-09-03",
    )

    assert captured_params["latitude"] == 28.6469
    assert captured_params["longitude"] == 77.3160
    assert captured_params["start_date"] == "2026-09-01"
    assert captured_params["end_date"] == "2026-09-03"
    assert captured_params["timezone"] == "UTC"
    assert "pm2_5" in captured_params["hourly"]


def test_historical_api_retry_on_transient_error(monkeypatch):
    """Verify client retries with backoff on transient network / 5xx errors."""
    attempts = 0

    def mock_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("Transient connection drop")
        return httpx.Response(
            status_code=200,
            json={"hourly": {"time": ["2026-09-01T00:00"], "pm2_5": [40.0]}},
        )

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    client = OpenMeteoClient()
    payload = client.fetch_historical_air_quality(
        latitude=28.6469,
        longitude=77.3160,
        start_date="2026-09-01",
        end_date="2026-09-01",
        max_retries=3,
        backoff_base=0.01,  # Fast backoff for testing
    )

    assert attempts == 3
    assert "hourly" in payload


def test_historical_api_rate_limit_handling(monkeypatch):
    """Verify HTTP 429 raises OpenMeteoRateLimitError."""
    def mock_get(*args, **kwargs):
        return httpx.Response(status_code=429, text="Rate limit exceeded")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    client = OpenMeteoClient()
    with pytest.raises(OpenMeteoRateLimitError) as exc_info:
        client.fetch_historical_air_quality(
            latitude=28.6469,
            longitude=77.3160,
            start_date="2026-09-01",
            end_date="2026-09-01",
            max_retries=1,
        )
    assert "rate limit exceeded" in str(exc_info.value)


def test_historical_chunking_merges_records(monkeypatch):
    """Verify long date ranges are queried in chunks and seamlessly combined."""
    queries = []

    def mock_get(self, url, params=None, **kwargs):
        queries.append((params["start_date"], params["end_date"]))
        # Generate 24 hours per day requested
        return httpx.Response(
            status_code=200,
            json={
                "hourly": {
                    "time": [f"{params['start_date']}T00:00"],
                    "pm2_5": [50.0],
                }
            },
        )

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    client = OpenMeteoClient()
    # 5 days with chunk_days=2 should produce 3 chunk queries (2 days + 2 days + 1 day)
    res = client.fetch_historical_air_quality(
        latitude=28.6469,
        longitude=77.3160,
        start_date="2026-09-01",
        end_date="2026-09-05",
        chunk_days=2,
    )

    assert len(queries) == 3
    assert queries[0] == ("2026-09-01", "2026-09-02")
    assert queries[1] == ("2026-09-03", "2026-09-04")
    assert queries[2] == ("2026-09-05", "2026-09-05")
    assert len(res["hourly"]["time"]) == 3


# -----------------------------------------------------------------------------
# 3. Database Ingestion & Idempotency Tests
# -----------------------------------------------------------------------------

def test_historical_ingestion_idempotency():
    """Verify historical ingestion can be run repeatedly without creating duplicates."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured.")

    db: Session = session_factory()
    try:
        sample_time = "2026-09-01T05:00"
        sample_payload = {
            "hourly": {
                "time": [sample_time],
                "pm2_5": [68.0],
                "pm10": [140.0],
                "nitrogen_dioxide": [18.5],
                "sulphur_dioxide": [14.0],
                "carbon_monoxide": [350.0],  # 0.35 mg/m³
                "ozone": [30.0],
            }
        }

        class MockHistoricalClient:
            def fetch_historical_air_quality(self, *args, **kwargs):
                return sample_payload

        station = SUPPORTED_STATIONS["anand-vihar"]

        # Run 1
        res1 = ingest_historical_open_meteo_data(
            db=db,
            start_date="2026-09-01",
            end_date="2026-09-01",
            client=MockHistoricalClient(),
            target_stations=[station],
        )
        assert res1.records_fetched == 1
        assert res1.normalized_estimates == 1

        # Run 2: duplicate check
        res2 = ingest_historical_open_meteo_data(
            db=db,
            start_date="2026-09-01",
            end_date="2026-09-01",
            client=MockHistoricalClient(),
            target_stations=[station],
        )
        assert res2.normalized_estimates == 1
        assert res2.estimates_inserted == 0
        assert res2.duplicates_skipped == 1

    finally:
        db.close()


def test_historical_ingestion_preserves_official_cpcb_readings():
    """
    CRITICAL: Verify that historical Open-Meteo ingestion strictly persists in
    modeled_air_quality_estimates and never inserts into or modifies air_quality_readings.
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured.")

    db: Session = session_factory()
    try:
        cpcb_count_before = db.query(AirQualityReading).count()

        sample_payload = {
            "hourly": {
                "time": ["2026-09-02T12:00"],
                "pm2_5": [95.0],
            }
        }

        class MockHistoricalClient:
            def fetch_historical_air_quality(self, *args, **kwargs):
                return sample_payload

        station = SUPPORTED_STATIONS["punjabi-bagh"]
        ingest_historical_open_meteo_data(
            db=db,
            start_date="2026-09-02",
            end_date="2026-09-02",
            client=MockHistoricalClient(),
            target_stations=[station],
        )

        cpcb_count_after = db.query(AirQualityReading).count()
        assert cpcb_count_after == cpcb_count_before

    finally:
        db.close()
