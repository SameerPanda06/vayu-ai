from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_forecast_missing_station_id_returns_422():
    response = client.get("/api/forecast")
    assert response.status_code == 422


def test_forecast_unsupported_station_returns_404():
    response = client.get("/api/forecast?station_id=unknown-station-xyz")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert body["detail"]["error"] == "StationNotFound"
    assert "supported_station_ids" in body["detail"]


def test_forecast_returns_72_ordered_records_and_metadata():
    station_id = "anand-vihar"
    response = client.get(f"/api/forecast?station_id={station_id}")
    assert response.status_code == 200
    data = response.json()

    # Response-level metadata checks
    assert data["data_mode"] == "synthetic_demo"
    assert "statement" in data
    assert "illustrative" in data["statement"].lower() or "unvalidated" in data["statement"].lower()
    assert "generated_at" in data

    # Units check
    units = data["units"]
    assert units["pm25"] == "µg/m³"
    assert units["temperature"] == "°C"
    assert units["wind_speed"] == "m/s"
    assert units["pbl_height"] == "m"

    # Station metadata check
    assert data["station"]["id"] == station_id

    # Exactly 72 records
    forecast = data["forecast"]
    assert len(forecast) == 72
    assert data["forecast_hours"] == 72

    # Verify temporal ordering and physical ranges
    for idx, record in enumerate(forecast):
        assert record["hour_index"] == idx
        # Ensure PM2.5 is not labeled as AQI
        assert "aqi" not in record

        # Bounds check
        assert 0.0 < record["pm25"] < 1000.0
        assert -10.0 < record["temperature_c"] < 60.0
        assert 0.0 <= record["wind_speed_ms"] < 40.0
        assert 50.0 < record["pbl_height_m"] < 5000.0

        ts = datetime.fromisoformat(record["timestamp_utc"].replace("Z", "+00:00"))
        if idx > 0:
            prev_ts = datetime.fromisoformat(forecast[idx - 1]["timestamp_utc"].replace("Z", "+00:00"))
            assert ts - prev_ts == timedelta(hours=1)


def test_forecast_is_deterministic():
    """Verify that identical queries produce identical values (fixed reference & seed)."""
    response1 = client.get("/api/forecast?station_id=punjabi-bagh")
    response2 = client.get("/api/forecast?station_id=punjabi-bagh")

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    assert data1["generated_at"] == data2["generated_at"]
    assert len(data1["forecast"]) == len(data2["forecast"]) == 72

    for r1, r2 in zip(data1["forecast"], data2["forecast"]):
        assert r1["hour_index"] == r2["hour_index"]
        assert r1["timestamp_utc"] == r2["timestamp_utc"]
        assert r1["pm25"] == r2["pm25"]
        assert r1["temperature_c"] == r2["temperature_c"]
        assert r1["wind_speed_ms"] == r2["wind_speed_ms"]
        assert r1["pbl_height_m"] == r2["pbl_height_m"]
