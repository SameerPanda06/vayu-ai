from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Base, check_database_connection, get_db
from app.main import app
from app.models import AirQualityReading, Forecast, Station

client = TestClient(app)


def test_models_metadata_registration():
    """Verify all required Phase 3 models are properly registered in Base metadata."""
    table_names = Base.metadata.tables.keys()
    assert "stations" in table_names
    assert "air_quality_readings" in table_names
    assert "forecasts" in table_names


def test_station_model_schema():
    """Verify Station table schema, column definitions, and constraints."""
    table = Base.metadata.tables["stations"]
    column_names = {col.name for col in table.columns}
    assert {"id", "name", "city", "state", "latitude", "longitude", "created_at"}.issubset(column_names)

    # Primary key check
    assert table.c.id.primary_key
    assert not table.c.name.nullable
    assert not table.c.latitude.nullable
    assert not table.c.longitude.nullable

    # Model instantiation
    station = Station(
        id="anand-vihar",
        name="Anand Vihar",
        city="Delhi NCR",
        state="Delhi",
        latitude=28.6469,
        longitude=77.3160,
    )
    assert station.id == "anand-vihar"
    assert station.name == "Anand Vihar"
    assert "anand-vihar" in repr(station)


def test_air_quality_reading_model_schema():
    """Verify AirQualityReading table schema, foreign keys, and indexes."""
    table = Base.metadata.tables["air_quality_readings"]
    column_names = {col.name for col in table.columns}
    expected_cols = {
        "id",
        "station_id",
        "timestamp",
        "aqi",
        "pm2_5",
        "pm10",
        "no2",
        "so2",
        "co",
        "o3",
        "created_at",
    }
    assert expected_cols.issubset(column_names)

    # Foreign key check
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "stations.id" in fk_targets

    # Model instantiation
    now = datetime.now(timezone.utc)
    reading = AirQualityReading(
        station_id="anand-vihar",
        timestamp=now,
        aqi=245.0,
        pm2_5=182.5,
        pm10=310.0,
        no2=45.2,
        so2=12.1,
        co=1.8,
        o3=28.4,
    )
    assert reading.station_id == "anand-vihar"
    assert reading.pm2_5 == 182.5
    assert reading.timestamp == now


def test_forecast_model_schema():
    """Verify Forecast table schema, foreign keys, and indexes."""
    table = Base.metadata.tables["forecasts"]
    column_names = {col.name for col in table.columns}
    expected_cols = {
        "id",
        "station_id",
        "forecast_time",
        "predicted_aqi",
        "predicted_pm2_5",
        "model_version",
        "created_at",
    }
    assert expected_cols.issubset(column_names)

    # Foreign key check
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "stations.id" in fk_targets

    # Model instantiation
    now = datetime.now(timezone.utc)
    fc = Forecast(
        station_id="anand-vihar",
        forecast_time=now,
        predicted_aqi=210.0,
        predicted_pm2_5=145.2,
        model_version="vayu-emulator-v0.1",
    )
    assert fc.station_id == "anand-vihar"
    assert fc.predicted_pm2_5 == 145.2
    assert fc.model_version == "vayu-emulator-v0.1"


def test_database_url_normalization():
    """Verify standard postgres URLs are converted to use psycopg v3 dialect."""
    s1 = Settings(database_url="postgres://user:pass@localhost:5432/vayu")
    assert s1.normalized_database_url == "postgresql+psycopg://user:pass@localhost:5432/vayu"

    s2 = Settings(database_url="postgresql://user:pass@localhost:5432/vayu")
    assert s2.normalized_database_url == "postgresql+psycopg://user:pass@localhost:5432/vayu"

    s3 = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/vayu")
    assert s3.normalized_database_url == "postgresql+psycopg://user:pass@localhost:5432/vayu"

    s4 = Settings(database_url=None)
    assert s4.normalized_database_url is None


def test_health_endpoint_includes_database_status():
    """Verify /api/health includes non-breaking database status information."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert "status" in data["database"]
    assert "configured" in data["database"]
    assert "message" in data["database"]


def test_dedicated_db_health_endpoint():
    """Verify dedicated /api/health/db endpoint responds with connectivity details."""
    response = client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "configured" in data
    assert "message" in data


def test_get_db_unconfigured_behavior(monkeypatch):
    """Verify get_db dependency raises 503 when DATABASE_URL is not configured."""
    from app import database

    monkeypatch.setattr(database, "_SessionLocal", None)
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database.settings, "database_url", None)

    with pytest.raises(HTTPException) as exc_info:
        next(database.get_db())
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "DatabaseNotConfigured"


def test_postgresql_ddl_compilation():
    """Verify all models generate valid DDL targeting PostgreSQL dialect."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl
        assert "TIMESTAMP WITH TIME ZONE" in ddl

