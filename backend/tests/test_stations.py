from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_stations_list():
    response = client.get("/api/stations")
    assert response.status_code == 200
    data = response.json()
    assert "stations" in data
    assert "count" in data
    assert data["count"] == len(data["stations"])
    assert data["count"] >= 4

    station_ids = [s["id"] for s in data["stations"]]
    assert "anand-vihar" in station_ids
    assert "mandir-marg" in station_ids
    assert "punjabi-bagh" in station_ids

    for station in data["stations"]:
        assert "id" in station and len(station["id"]) > 0
        assert "name" in station and len(station["name"]) > 0
        assert "latitude" in station and 28.0 <= station["latitude"] <= 29.5
        assert "longitude" in station and 76.5 <= station["longitude"] <= 78.0
        assert "city" in station
        assert "state" in station
        assert "description" in station
