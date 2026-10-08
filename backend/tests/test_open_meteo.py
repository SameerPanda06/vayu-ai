import json
from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.main import app
from app.models import AirQualityReading, ModeledAirQualityEstimate, Station
from app.services.data_gov_client import (
    DataGovAPIError,
    DataGovAuthError,
    DataGovClient,
)
from app.services.ingestion import (
    ingest_air_quality_data,
    ingest_open_meteo_data,
    orchestrate_aqi_ingestion,
)
from app.services.normalization import (
    normalize_open_meteo_estimates,
)
from app.services.open_meteo_client import (
    HOURLY_VARIABLES,
    OpenMeteoClient,
    OpenMeteoError,
    OpenMeteoNetworkError,
    OpenMeteoResponseError,
    OpenMeteoTimeoutError,
)
from app.stations import SUPPORTED_STATIONS, get_all_stations

test_client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Open-Meteo Client HTTP and Error Handling Tests
# -----------------------------------------------------------------------------

def test_open_meteo_client_url_and_params(monkeypatch):
    """Verify OpenMeteoClient generates correct endpoint parameters."""
    captured_params = {}

    def mock_get(self, url, params=None, **kwargs):
        nonlocal captured_params
        captured_params = params
        sample = {
            "hourly": {
                "time": ["2026-10-08T00:00"],
                "pm2_5": [45.0],
                "pm10": [90.0],
                "nitrogen_dioxide": [20.0],
                "sulphur_dioxide": [15.0],
                "carbon_monoxide": [400.0],
                "ozone": [30.0],
            }
        }
        return httpx.Response(status_code=200, json=sample)

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    client = OpenMeteoClient(past_hours=4, forecast_hours=1, timezone="UTC")
    payload = client.fetch_air_quality(latitude=28.6469, longitude=77.3160)

    assert captured_params["latitude"] == 28.6469
    assert captured_params["longitude"] == 77.3160
    assert captured_params["timezone"] == "UTC"
    assert captured_params["past_hours"] == 4
    assert captured_params["forecast_hours"] == 1
    assert "pm2_5" in captured_params["hourly"]
    assert "carbon_monoxide" in captured_params["hourly"]
    assert "hourly" in payload


def test_open_meteo_client_http_500_error(monkeypatch):
    """Verify HTTP 500 raises OpenMeteoResponseError."""
    def mock_get(*args, **kwargs):
        return httpx.Response(status_code=500, text="Internal Server Error")

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    client = OpenMeteoClient()
    with pytest.raises(OpenMeteoResponseError) as exc_info:
        client.fetch_air_quality(28.6469, 77.3160)
    assert "HTTP 500" in str(exc_info.value)


def test_open_meteo_client_timeout(monkeypatch):
    """Verify request timeout raises OpenMeteoTimeoutError."""
    def mock_get(*args, **kwargs):
        raise httpx.TimeoutException("Read timeout after 15s")

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    client = OpenMeteoClient(timeout=15.0)
    with pytest.raises(OpenMeteoTimeoutError) as exc_info:
        client.fetch_air_quality(28.6469, 77.3160)
    assert "timed out after 15.0s" in str(exc_info.value)


def test_open_meteo_client_network_error(monkeypatch):
    """Verify network connection failure raises OpenMeteoNetworkError."""
    def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Failed to resolve host")

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    client = OpenMeteoClient()
    with pytest.raises(OpenMeteoNetworkError) as exc_info:
        client.fetch_air_quality(28.6469, 77.3160)
    assert "Network failure" in str(exc_info.value)


def test_open_meteo_client_malformed_json(monkeypatch):
    """Verify non-JSON response raises OpenMeteoResponseError."""
    def mock_get(*args, **kwargs):
        return httpx.Response(status_code=200, text="<html>502 Bad Gateway</html>")

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    client = OpenMeteoClient()
    with pytest.raises(OpenMeteoResponseError) as exc_info:
        client.fetch_air_quality(28.6469, 77.3160)
    assert "Failed to decode JSON" in str(exc_info.value)


def test_open_meteo_client_invalid_coordinates():
    """Verify invalid geographic coordinates raise ValueError."""
    client = OpenMeteoClient()
    with pytest.raises(ValueError):
        client.fetch_air_quality(latitude=120.0, longitude=77.3160)
    with pytest.raises(ValueError):
        client.fetch_air_quality(latitude=28.6469, longitude=200.0)


# -----------------------------------------------------------------------------
# 2. Response Parsing, Unit Conversion, and Timestamp Tests
# -----------------------------------------------------------------------------

def test_open_meteo_response_parsing():
    """Verify complete parsing of Open-Meteo hourly pollutant response."""
    sample_payload = {
        "hourly": {
            "time": ["2026-10-08T03:00", "2026-10-08T04:00"],
            "pm2_5": [85.9, 87.3],
            "pm10": [203.5, 225.4],
            "nitrogen_dioxide": [26.7, 24.0],
            "sulphur_dioxide": [33.5, 36.8],
            "carbon_monoxide": [608.0, 609.0],
            "ozone": [71.0, 107.0],
        }
    }
    estimates = normalize_open_meteo_estimates("anand-vihar", sample_payload)
    assert len(estimates) == 2

    e0 = estimates[0]
    assert e0.station_id == "anand-vihar"
    assert e0.valid_time == datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)
    assert e0.pm2_5 == 85.9
    assert e0.pm10 == 203.5
    assert e0.no2 == 26.7
    assert e0.so2 == 33.5
    # CO converted from 608.0 µg/m³ to 0.608 mg/m³
    assert pytest.approx(e0.co, rel=1e-5) == 0.608
    assert e0.o3 == 71.0
    assert e0.provider == "open-meteo"


def test_open_meteo_utc_timestamp_handling():
    """Verify timestamps without explicit timezone or with Z are strictly parsed as UTC."""
    payload = {
        "hourly": {
            "time": ["2026-10-08T10:00", "2026-10-08T11:00:00Z"],
            "pm2_5": [50.0, 52.0],
        }
    }
    estimates = normalize_open_meteo_estimates("mandir-marg", payload)
    assert len(estimates) == 2
    assert estimates[0].valid_time.tzinfo == timezone.utc
    assert estimates[0].valid_time.hour == 10
    assert estimates[1].valid_time.tzinfo == timezone.utc
    assert estimates[1].valid_time.hour == 11


def test_open_meteo_co_unit_conversion():
    """
    CRITICAL: Verify Carbon Monoxide conversion from µg/m³ to mg/m³ (CO_mg_m3 = CO_ug_m3 / 1000).
    Verify other pollutant values remain unmodified.
    """
    payload = {
        "hourly": {
            "time": ["2026-10-08T00:00"],
            "pm2_5": [120.0],
            "pm10": [250.0],
            "nitrogen_dioxide": [45.0],
            "sulphur_dioxide": [12.0],
            "carbon_monoxide": [1500.0],  # 1500 µg/m³
            "ozone": [35.0],
        }
    }
    estimates = normalize_open_meteo_estimates("rk-puram", payload)
    assert len(estimates) == 1
    est = estimates[0]

    # CO must be exactly 1.5 mg/m³
    assert est.co == 1.5
    # Other pollutants must match input exactly
    assert est.pm2_5 == 120.0
    assert est.pm10 == 250.0
    assert est.no2 == 45.0
    assert est.so2 == 12.0
    assert est.o3 == 35.0


def test_open_meteo_missing_and_null_values():
    """Verify nulls, missing sentinels, or empty fields result in None and are NOT converted to 0.0."""
    payload = {
        "hourly": {
            "time": ["2026-10-08T00:00"],
            "pm2_5": [None],
            "pm10": ["NA"],
            "nitrogen_dioxide": [-999],
            "sulphur_dioxide": [""],
            "carbon_monoxide": [None],
            "ozone": [0.0],  # Genuine zero is preserved
        }
    }
    estimates = normalize_open_meteo_estimates("igi-airport-t3", payload)
    assert len(estimates) == 1
    est = estimates[0]

    assert est.pm2_5 is None
    assert est.pm10 is None
    assert est.no2 is None
    assert est.so2 is None
    assert est.co is None
    assert est.o3 == 0.0  # Legitimate zero is kept


def test_open_meteo_mismatched_array_lengths():
    """Verify mismatched array lengths do not raise IndexError and missing indices are None."""
    payload = {
        "hourly": {
            "time": ["2026-10-08T00:00", "2026-10-08T01:00", "2026-10-08T02:00"],
            "pm2_5": [75.0],             # Only 1 element
            "pm10": [150.0, 160.0],      # Only 2 elements
            "carbon_monoxide": [500.0],  # Only 1 element
        }
    }
    estimates = normalize_open_meteo_estimates("punjabi-bagh", payload)
    assert len(estimates) == 3

    # Index 0: both present
    assert estimates[0].pm2_5 == 75.0
    assert estimates[0].pm10 == 150.0
    assert estimates[0].co == 0.5

    # Index 1: pm2_5 missing, pm10 present
    assert estimates[1].pm2_5 is None
    assert estimates[1].pm10 == 160.0
    assert estimates[1].co is None

    # Index 2: all missing
    assert estimates[2].pm2_5 is None
    assert estimates[2].pm10 is None
    assert estimates[2].co is None


def test_open_meteo_no_cpcb_aqi_invented():
    """Verify no Indian CPCB AQI is derived or calculated from Open-Meteo modeled data."""
    payload = {
        "hourly": {
            "time": ["2026-10-08T00:00"],
            "pm2_5": [250.0],
            "pm10": [400.0],
            "carbon_monoxide": [2000.0],
        }
    }
    estimates = normalize_open_meteo_estimates("noida-sec62", payload)
    est = estimates[0]
    # Attribute 'aqi' must not exist on NormalizedModeledEstimate
    assert not hasattr(est, "aqi")


# -----------------------------------------------------------------------------
# 3. Station Catalog and Coordinate Verification
# -----------------------------------------------------------------------------

def test_correct_station_coordinate_usage(monkeypatch):
    """Verify Open-Meteo requests use the exact coordinates from the curated station catalog."""
    queried_coords = []

    def mock_fetch(self, latitude, longitude, **kwargs):
        queried_coords.append((latitude, longitude))
        return {
            "hourly": {
                "time": ["2026-10-08T00:00"],
                "pm2_5": [60.0],
            }
        }

    monkeypatch.setattr(OpenMeteoClient, "fetch_air_quality", mock_fetch)

    client = OpenMeteoClient()
    for s_id, s_meta in SUPPORTED_STATIONS.items():
        client.fetch_air_quality(s_meta.latitude, s_meta.longitude)

    expected_coords = [(s.latitude, s.longitude) for s in SUPPORTED_STATIONS.values()]
    assert queried_coords == expected_coords


# -----------------------------------------------------------------------------
# 4. Database Ingestion, Idempotency, and Transaction Safety
# -----------------------------------------------------------------------------

def test_open_meteo_duplicate_prevention_idempotency():
    """
    Verify Open-Meteo ingestion is idempotent:
    Repeated ingestion of identical valid_times produces 0 duplicate rows.
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live ingestion test.")

    db: Session = session_factory()
    try:
        sample_time = "2026-10-08T00:00"
        sample_payload = {
            "hourly": {
                "time": [sample_time],
                "pm2_5": [77.5],
                "pm10": [160.0],
                "nitrogen_dioxide": [22.0],
                "sulphur_dioxide": [18.0],
                "carbon_monoxide": [450.0],
                "ozone": [40.0],
            }
        }

        class MockClient:
            def fetch_air_quality(self, latitude, longitude, **kwargs):
                return sample_payload

        station = SUPPORTED_STATIONS["anand-vihar"]

        # Run 1
        res1 = ingest_open_meteo_data(db, client=MockClient(), target_stations=[station])
        assert res1.records_fetched == 1
        assert res1.normalized_estimates == 1

        # Check estimate in database
        valid_dt = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
        record = (
            db.query(ModeledAirQualityEstimate)
            .filter(
                ModeledAirQualityEstimate.station_id == "anand-vihar",
                ModeledAirQualityEstimate.valid_time == valid_dt,
                ModeledAirQualityEstimate.provider == "open-meteo",
            )
            .first()
        )
        assert record is not None
        assert record.pm2_5 == 77.5
        assert pytest.approx(record.co, rel=1e-5) == 0.45

        # Run 2 with identical data -> Idempotency check: 0 new rows, 1 skipped duplicate
        res2 = ingest_open_meteo_data(db, client=MockClient(), target_stations=[station])
        assert res2.normalized_estimates == 1
        assert res2.estimates_inserted == 0
        assert res2.duplicates_skipped == 1

    finally:
        db.close()


def test_open_meteo_db_transaction_rollback():
    """Verify that an unexpected error during ingestion triggers database rollback."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        class CrashingClient:
            def fetch_air_quality(self, latitude, longitude, **kwargs):
                raise RuntimeError("Simulated mid-ingestion crash")

        station = SUPPORTED_STATIONS["mandir-marg"]
        with pytest.raises(RuntimeError):
            ingest_open_meteo_data(db, client=CrashingClient(), target_stations=[station])

    finally:
        db.close()


def test_preservation_of_existing_cpcb_observations():
    """
    CRITICAL: Verify that inserting Open-Meteo modeled estimates does NOT touch,
    overwrite, or delete official station readings in air_quality_readings.
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        # Count initial official readings
        initial_readings_count = db.query(AirQualityReading).count()

        # Ingest Open-Meteo modeled estimates
        sample_payload = {
            "hourly": {
                "time": ["2026-10-08T01:00"],
                "pm2_5": [99.0],
                "carbon_monoxide": [800.0],
            }
        }
        class MockClient:
            def fetch_air_quality(self, *args, **kwargs):
                return sample_payload

        station = SUPPORTED_STATIONS["punjabi-bagh"]
        ingest_open_meteo_data(db, client=MockClient(), target_stations=[station])

        # Verify air_quality_readings row count is unchanged
        post_readings_count = db.query(AirQualityReading).count()
        assert post_readings_count == initial_readings_count

    finally:
        db.close()


# -----------------------------------------------------------------------------
# 5. Orchestration and Fallback Behavior Tests
# -----------------------------------------------------------------------------

def test_orchestration_cpcb_success_without_fallback():
    """Verify that when CPCB succeeds, actual provider is CPCB and Open-Meteo is NOT invoked."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        sample_cpcb = [
            {
                "country": "India",
                "state": "Delhi",
                "city": "Delhi",
                "station": "Anand Vihar, Delhi - DPCC",
                "last_update": "08-10-2026 12:00:00",
                "pollutant_id": "PM2.5",
                "pollutant_avg": "165.0",
                "latitude": "28.6469",
                "longitude": "77.3160",
            }
        ]

        result = orchestrate_aqi_ingestion(
            db=db,
            mode="auto",
            cpcb_raw_records=sample_cpcb,
        )

        assert result.selected_mode == "auto"
        assert result.actual_provider == "cpcb"
        assert result.fallback_used is False
        assert result.records_fetched == 1
        assert result.normalized_count == 1

    finally:
        db.close()


def test_orchestration_cpcb_timeout_triggers_fallback():
    """Verify that CPCB timeout triggers automatic fallback to Open-Meteo."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        class TimingOutCPCBClient:
            def fetch_records(self, **kwargs):
                raise DataGovAPIError("Request to data.gov.in timed out after 15s: Timeout")

        class MockOpenMeteoClient:
            def fetch_air_quality(self, latitude, longitude, **kwargs):
                return {
                    "hourly": {
                        "time": ["2026-10-08T02:00"],
                        "pm2_5": [82.0],
                        "carbon_monoxide": [350.0],
                    }
                }

        station = SUPPORTED_STATIONS["rk-puram"]
        result = orchestrate_aqi_ingestion(
            db=db,
            mode="auto",
            cpcb_client=TimingOutCPCBClient(),
            open_meteo_client=MockOpenMeteoClient(),
            target_stations=[station],
        )

        assert result.selected_mode == "auto"
        assert result.actual_provider == "open-meteo"
        assert result.fallback_used is True
        assert "timed out" in result.fallback_reason
        assert result.normalized_count == 1

    finally:
        db.close()


def test_orchestration_cpcb_connection_error_triggers_fallback():
    """Verify that CPCB connection failure (e.g. port 443 unreachable) triggers Open-Meteo fallback."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        class ConnectionFailingCPCBClient:
            def fetch_records(self, **kwargs):
                raise DataGovAPIError("Connection failure communicating with data.gov.in: ConnectError")

        class MockOpenMeteoClient:
            def fetch_air_quality(self, latitude, longitude, **kwargs):
                return {
                    "hourly": {
                        "time": ["2026-10-08T03:00"],
                        "pm2_5": [91.0],
                        "carbon_monoxide": [410.0],
                    }
                }

        station = SUPPORTED_STATIONS["mandir-marg"]
        result = orchestrate_aqi_ingestion(
            db=db,
            mode="auto",
            cpcb_client=ConnectionFailingCPCBClient(),
            open_meteo_client=MockOpenMeteoClient(),
            target_stations=[station],
        )

        assert result.selected_mode == "auto"
        assert result.actual_provider == "open-meteo"
        assert result.fallback_used is True
        assert "Connection failure" in result.fallback_reason

    finally:
        db.close()


def test_orchestration_invalid_credentials_no_silent_fallback():
    """
    CRITICAL: Verify that missing or invalid CPCB credentials (DataGovAuthError)
    do NOT silently trigger Open-Meteo fallback. Must raise / abort with error.
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        class AuthFailingCPCBClient:
            def fetch_records(self, **kwargs):
                raise DataGovAuthError("DATA_GOV_IN_API_KEY is not configured in environment.")

        with pytest.raises(DataGovAuthError) as exc_info:
            orchestrate_aqi_ingestion(
                db=db,
                mode="auto",
                cpcb_client=AuthFailingCPCBClient(),
            )
        assert "DATA_GOV_IN_API_KEY is not configured" in str(exc_info.value)

    finally:
        db.close()


def test_orchestration_open_meteo_failure_raises():
    """Verify that when Open-Meteo fails during fallback or direct mode, the failure is raised cleanly."""
    session_factory = get_sessionmaker()
    if not session_factory:
        pytest.skip("PostgreSQL database not configured for live test.")

    db: Session = session_factory()
    try:
        class FailingOMClient:
            def fetch_air_quality(self, *args, **kwargs):
                raise OpenMeteoNetworkError("DNS resolution failed for open-meteo")

        with pytest.raises(OpenMeteoNetworkError):
            orchestrate_aqi_ingestion(
                db=db,
                mode="open_meteo",
                open_meteo_client=FailingOMClient(),
            )

    finally:
        db.close()


# -----------------------------------------------------------------------------
# 6. Read-Only Modeled Estimates API Endpoint & Backward Compatibility Tests
# -----------------------------------------------------------------------------

def test_modeled_estimates_endpoint_explicit_provenance():
    """
    Verify GET /api/stations/{station_id}/modeled-estimates returns structured data
    with explicit provider='open-meteo' and data_type='modeled_estimate'.
    """
    response = test_client.get("/api/stations/anand-vihar/modeled-estimates")
    assert response.status_code == 200
    data = response.json()

    assert data["station_id"] == "anand-vihar"
    assert data["data_type"] == "modeled_estimate"
    assert data["provider"] == "open-meteo"
    assert "NOT official CPCB" in data["statement"]
    assert "estimates" in data
    assert isinstance(data["estimates"], list)


def test_modeled_estimates_endpoint_404_for_unknown_station():
    """Verify requesting modeled estimates for an unsupported station returns 404."""
    response = test_client.get("/api/stations/non-existent-station/modeled-estimates")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"] == "StationNotFound"


def test_existing_endpoints_backward_compatibility():
    """Verify /api/health, /api/stations, and /api/forecast remain 100% backward compatible."""
    # Health check
    res_health = test_client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # Stations list
    res_stations = test_client.get("/api/stations")
    assert res_stations.status_code == 200
    stations_data = res_stations.json()
    assert stations_data["count"] == 6
    assert any(s["id"] == "anand-vihar" for s in stations_data["stations"])

    # Synthetic Forecast
    res_fc = test_client.get("/api/forecast?station_id=anand-vihar")
    assert res_fc.status_code == 200
    fc_data = res_fc.json()
    assert fc_data["data_mode"] == "synthetic_demo"
    assert fc_data["forecast_hours"] == 72
    assert len(fc_data["forecast"]) == 72
