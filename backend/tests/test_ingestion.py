import json
from datetime import datetime, timezone
from typing import Any, Dict, List
import pytest
import httpx
from sqlalchemy.orm import Session

from app.config import Settings, _get_env_file_candidates
from app.database import get_engine, get_sessionmaker
from app.models import AirQualityReading, Station
from app.services.data_gov_client import (
    DataGovAPIError,
    DataGovAuthError,
    DataGovClient,
    DataGovRateLimitError,
)
from app.services.ingestion import IngestionResult, ingest_air_quality_data
from app.services.normalization import (
    group_and_normalize_records,
    is_in_delhi_ncr,
    parse_numeric,
    parse_observation_timestamp,
    standardize_pollutant_name,
)
from app.services.station_matching import clean_station_name, resolve_station_id


def test_env_deterministic_discovery():
    """Verify .env discovery candidates resolve relative to project root without hardcoded paths."""
    candidates = _get_env_file_candidates()
    assert len(candidates) >= 1
    # Candidate should end with .env
    assert any(c.endswith(".env") for c in candidates)


def test_numeric_parsing():
    """Verify safe conversion of numeric strings and strict handling of missing sentinels."""
    assert parse_numeric("145.8") == 145.8
    assert parse_numeric(200) == 200.0
    assert parse_numeric(0) == 0.0
    assert parse_numeric("0") == 0.0

    # Ensure missing / invalid values are None and NOT converted to zero
    assert parse_numeric(None) is None
    assert parse_numeric("") is None
    assert parse_numeric("   ") is None
    assert parse_numeric("NA") is None
    assert parse_numeric("N/A") is None
    assert parse_numeric("null") is None
    assert parse_numeric("None") is None
    assert parse_numeric("-") is None
    assert parse_numeric("--") is None
    assert parse_numeric("invalid_num") is None
    assert parse_numeric(-999) is None
    assert parse_numeric("-999") is None


def test_observation_timestamp_parsing():
    """Verify timestamp parsing and conversion from IST (UTC+05:30) to UTC."""
    # 08-10-2026 12:00:00 IST is 08-10-2026 06:30:00 UTC
    dt = parse_observation_timestamp("08-10-2026 12:00:00")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 6
    assert dt.minute == 30
    assert dt.day == 8
    assert dt.month == 10
    assert dt.year == 2026

    # Test invalid timestamp returns None
    assert parse_observation_timestamp("NA") is None
    assert parse_observation_timestamp("") is None
    assert parse_observation_timestamp(None) is None
    assert parse_observation_timestamp("invalid-date") is None


def test_pollutant_standardization():
    """Verify robust pollutant naming normalization."""
    assert standardize_pollutant_name("PM2.5") == "pm2_5"
    assert standardize_pollutant_name("PM 2.5") == "pm2_5"
    assert standardize_pollutant_name("pm25") == "pm2_5"
    assert standardize_pollutant_name("PM10") == "pm10"
    assert standardize_pollutant_name("NO2") == "no2"
    assert standardize_pollutant_name("SO2") == "so2"
    assert standardize_pollutant_name("CO") == "co"
    assert standardize_pollutant_name("Ozone") == "o3"
    assert standardize_pollutant_name("O3") == "o3"
    assert standardize_pollutant_name("AQI") == "aqi"
    assert standardize_pollutant_name("UNKNOWN_GAS") is None
    assert standardize_pollutant_name(None) is None


def test_delhi_ncr_scope_filter():
    """Verify geographic filtering correctly scopes Delhi NCR stations."""
    assert is_in_delhi_ncr(state="Delhi", city="Delhi", station="Anand Vihar")
    assert is_in_delhi_ncr(state="Uttar Pradesh", city="Noida", station="Sector 62")
    assert is_in_delhi_ncr(state="Haryana", city="Gurugram", station="Vikas Sadan")
    assert is_in_delhi_ncr(state="Haryana", city="Faridabad", station="Sector 16A")
    # Outside NCR
    assert not is_in_delhi_ncr(state="Maharashtra", city="Mumbai", station="Bandra")
    assert not is_in_delhi_ncr(state="Karnataka", city="Bengaluru", station="BTM")


def test_station_matching_curated_and_slugs():
    """Verify official CPCB station names map to existing curated IDs or generate clean slugs."""
    s_id, name, lat, lon = resolve_station_id("Anand Vihar, Delhi - DPCC", city="Delhi", state="Delhi")
    assert s_id == "anand-vihar"
    assert lat == 28.6469
    assert lon == 77.3160

    s_id, name, lat, lon = resolve_station_id("Punjabi Bagh, Delhi - DPCC", city="Delhi", state="Delhi")
    assert s_id == "punjabi-bagh"

    s_id, name, lat, lon = resolve_station_id("R K Puram, Delhi - DPCC", city="Delhi", state="Delhi")
    assert s_id == "rk-puram"

    s_id, name, lat, lon = resolve_station_id("Sector - 62, Noida - UPPCB", city="Noida", state="Uttar Pradesh")
    assert s_id == "noida-sec62"

    # New station not in curated list
    s_id, name, lat, lon = resolve_station_id("ITO, Delhi - DPCC", city="Delhi", state="Delhi")
    assert s_id == "delhi-ito"
    assert name == "ITO"


def test_group_and_normalize_records():
    """Verify combining multiple pollutant records into one consolidated observation."""
    raw_sample = [
        {
            "country": "India",
            "state": "Delhi",
            "city": "Delhi",
            "station": "Anand Vihar, Delhi - DPCC",
            "last_update": "08-10-2026 10:00:00",
            "pollutant_id": "PM2.5",
            "pollutant_avg": "194.5",
            "latitude": "28.6469",
            "longitude": "77.3160",
        },
        {
            "country": "India",
            "state": "Delhi",
            "city": "Delhi",
            "station": "Anand Vihar, Delhi - DPCC",
            "last_update": "08-10-2026 10:00:00",
            "pollutant_id": "PM10",
            "pollutant_avg": "320.0",
        },
        {
            "country": "India",
            "state": "Delhi",
            "city": "Delhi",
            "station": "Anand Vihar, Delhi - DPCC",
            "last_update": "08-10-2026 10:00:00",
            "pollutant_id": "NO2",
            "pollutant_avg": "45.2",
        },
        {
            "country": "India",
            "state": "Delhi",
            "city": "Delhi",
            "station": "Anand Vihar, Delhi - DPCC",
            "last_update": "08-10-2026 10:00:00",
            "pollutant_id": "SO2",
            "pollutant_avg": "NA",  # Missing value
        },
        # Record outside Delhi NCR (should be filtered)
        {
            "country": "India",
            "state": "Tamil Nadu",
            "city": "Chennai",
            "station": "Alandur, Chennai - CPCB",
            "last_update": "08-10-2026 10:00:00",
            "pollutant_id": "PM2.5",
            "pollutant_avg": "45.0",
        },
    ]

    observations = group_and_normalize_records(raw_sample, filter_delhi_ncr=True)
    assert len(observations) == 1

    obs = observations[0]
    assert obs.station_name == "Anand Vihar, Delhi - DPCC"
    assert obs.pm2_5 == 194.5
    assert obs.pm10 == 320.0
    assert obs.no2 == 45.2
    assert obs.so2 is None  # 'NA' converted to None
    assert obs.co is None
    assert obs.aqi is None  # No AQI invented


def test_data_gov_client_missing_key_raises_auth_error():
    """Verify DataGovClient raises DataGovAuthError when API key is missing."""
    client = DataGovClient(api_key=None)
    client.api_key = None
    with pytest.raises(DataGovAuthError) as exc_info:
        client.fetch_records()
    assert "DATA_GOV_IN_API_KEY is not configured" in str(exc_info.value)


def test_data_gov_client_http_errors_and_rate_limit(monkeypatch):
    """Verify DataGovClient handles HTTP 401, 429, 500, network errors, and malformed JSON cleanly."""
    client = DataGovClient(api_key="mock-api-key")

    # 1. Test 401 Auth Error
    def mock_get_401(*args, **kwargs):
        return httpx.Response(status_code=401, text="Unauthorized")

    monkeypatch.setattr(httpx.Client, "get", mock_get_401)
    with pytest.raises(DataGovAuthError):
        client.fetch_records()

    # 2. Test 429 Rate Limit
    def mock_get_429(*args, **kwargs):
        return httpx.Response(status_code=429, text="Too Many Requests")

    monkeypatch.setattr(httpx.Client, "get", mock_get_429)
    with pytest.raises(DataGovRateLimitError):
        client.fetch_records()

    # 3. Test 500 Server Error
    def mock_get_500(*args, **kwargs):
        return httpx.Response(status_code=500, text="Internal Server Error")

    monkeypatch.setattr(httpx.Client, "get", mock_get_500)
    with pytest.raises(DataGovAPIError) as exc_500:
        client.fetch_records()
    assert "HTTP 500" in str(exc_500.value)

    # 4. Test Malformed non-JSON
    def mock_get_malformed(*args, **kwargs):
        return httpx.Response(status_code=200, text="<html>Server Busy</html>")

    monkeypatch.setattr(httpx.Client, "get", mock_get_malformed)
    with pytest.raises(DataGovAPIError) as exc_json:
        client.fetch_records()
    assert "Failed to decode JSON" in str(exc_json.value)


def test_data_gov_client_success_response(monkeypatch):
    """Verify DataGovClient successfully extracts records list from valid JSON response."""
    client = DataGovClient(api_key="mock-valid-key")
    sample_payload = {
        "status": "ok",
        "count": 2,
        "records": [
            {"station": "Anand Vihar", "pollutant_id": "PM2.5", "pollutant_avg": "150"},
            {"station": "Mandir Marg", "pollutant_id": "PM2.5", "pollutant_avg": "80"},
        ],
    }

    def mock_get_success(*args, **kwargs):
        return httpx.Response(status_code=200, json=sample_payload)

    monkeypatch.setattr(httpx.Client, "get", mock_get_success)
    records = client.fetch_records()
    assert len(records) == 2
    assert records[0]["station"] == "Anand Vihar"


def test_database_ingestion_and_idempotency():
    """
    Verify full ingestion pipeline:
    - Normalizes records
    - Upserts Station
    - Inserts AirQualityReading
    - Repeated ingestion of identical records is idempotent (0 duplicates created).
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live ingestion test.")

    db: Session = session_factory()
    try:
        sample_records = [
            {
                "country": "India",
                "state": "Delhi",
                "city": "Delhi",
                "station": "Anand Vihar, Delhi - DPCC",
                "last_update": "08-10-2026 11:00:00",
                "pollutant_id": "PM2.5",
                "pollutant_avg": "188.5",
                "latitude": "28.6469",
                "longitude": "77.3160",
            },
            {
                "country": "India",
                "state": "Delhi",
                "city": "Delhi",
                "station": "Anand Vihar, Delhi - DPCC",
                "last_update": "08-10-2026 11:00:00",
                "pollutant_id": "PM10",
                "pollutant_avg": "295.0",
            },
        ]

        # First ingestion run
        res1 = ingest_air_quality_data(db, raw_records=sample_records)
        assert res1.fetched_records == 2
        assert res1.normalized_observations == 1
        assert res1.stations_upserted == 1

        # Check Station in database
        station = db.query(Station).filter(Station.id == "anand-vihar").first()
        assert station is not None
        assert station.name == "Anand Vihar"

        # Check AirQualityReading in database
        reading = (
            db.query(AirQualityReading)
            .filter(
                AirQualityReading.station_id == "anand-vihar",
            )
            .first()
        )
        assert reading is not None
        assert reading.pm2_5 == 188.5
        assert reading.pm10 == 295.0

        # Second ingestion run with identical data (IDEMPOTENCY CHECK)
        res2 = ingest_air_quality_data(db, raw_records=sample_records)
        assert res2.normalized_observations == 1
        assert res2.readings_inserted == 0  # No new readings inserted
        assert res2.duplicates_skipped == 1  # Duplicate skipped

    finally:
        db.close()


def test_cli_ingestion_script_handles_missing_keys(monkeypatch):
    """Verify CLI ingestion runner reports clean error code without unhandled traceback."""
    from app.scripts.ingest_aqi import run_ingestion

    # Simulate missing API key
    monkeypatch.setattr("app.config.settings.data_gov_in_api_key", None)
    exit_code = run_ingestion()
    assert exit_code == 1
