"""
Unit and integration tests for Phase 4 Step 3: Experimental ML Forecast API.

Tests:
1. Valid experimental response schema (+24h, +48h, +72h).
2. Correct validation-selected model routing (Ridge vs Persistence).
3. Stale data rejection (prevents serving 2024 data as live 2026 forecasts).
4. Insufficient history rejection (< 72 hours continuous lag history).
5. Feature schema mismatch rejection (44 required features).
6. Missing / corrupted model artifact rejection.
7. Unsupported station 404.
8. Anti-leakage verification (future records t > t_0 never affect t_0 prediction).
9. Nonnegative PM2.5 output clamping.
10. Preservation of existing operational synthetic forecast endpoint.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import _SessionLocal
from app.main import app
from app.models import ModeledAirQualityEstimate
from app.schemas import ExperimentalForecastResponse
from app.services.experimental_inference import (
    DEFAULT_ARTIFACT_DIR,
    generate_experimental_forecast,
)
from app.stations import get_station_by_id


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db_session() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Valid Experimental Response Schema
# ---------------------------------------------------------------------------
def test_experimental_forecast_valid_response_schema(client: TestClient) -> None:
    """Verify endpoint returns complete, compliant ExperimentalForecastResponse schema."""
    # Use known complete historical anchor with 72h continuous history
    ref_time = "2024-12-15T12:00:00Z"
    resp = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={ref_time}")

    assert resp.status_code == 200
    data = resp.json()

    # Top-level response metadata
    assert data["status"] == "experimental"
    assert data["is_experimental"] is True
    assert data["station_id"] == "anand-vihar"
    assert data["station_name"] == "Anand Vihar"
    assert data["prediction_time_utc"] == "2024-12-15T12:00:00Z"
    assert data["target_pollutant"] == "pm2_5"
    assert data["units"] == "µg/m³"
    assert data["forecast_structure"] == "discrete_milestones_24h_48h_72h"
    assert "hourly_sequence_note" in data
    assert "CAMS Global" in data["data_product"]
    assert "Open-Meteo" in data["data_provider"]
    assert "Experimental ML baseline forecast" in data["disclaimer"]
    assert data["training_period"]["start_utc"] == "2024-10-01T00:00:00Z"
    assert data["training_period"]["end_utc"] == "2024-12-29T23:00:00Z"

    # Validate 3 horizons: +24h, +48h, +72h
    horizons = data["horizons"]
    assert len(horizons) == 3

    h_map = {h["horizon_hours"]: h for h in horizons}
    assert 24 in h_map and 48 in h_map and 72 in h_map

    for h_hours in (24, 48, 72):
        item = h_map[h_hours]
        assert item["horizon_label"] == f"+{h_hours}h"
        expected_target_time = (
            datetime.fromisoformat(ref_time.replace("Z", "+00:00")) + timedelta(hours=h_hours)
        ).isoformat().replace("+00:00", "Z")
        assert item["target_time_utc"] == expected_target_time
        assert isinstance(item["predicted_pm2_5"], (int, float))
        assert item["predicted_pm2_5"] >= 0.0
        assert item["selected_model"] in ("ridge", "persistence", "seasonal_aligned")
        assert item["model_type"] is not None
        assert item["artifact_id"] is not None
        assert item["validation_mae"] is not None
        assert item["validation_mae"] > 0.0


# ---------------------------------------------------------------------------
# 2. Correct Validation-Selected Model Routing
# ---------------------------------------------------------------------------
def test_validation_selected_model_routing_anand_vihar(client: TestClient) -> None:
    """
    Verify Anand Vihar validation model routing:
    +24h -> Ridge (alpha=100)
    +48h -> Ridge (alpha=500)
    +72h -> Persistence (y(t_0))
    """
    ref_time = "2024-12-15T12:00:00Z"
    resp = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()
    h_map = {h["horizon_hours"]: h for h in data["horizons"]}

    # +24h should route to Ridge
    assert h_map[24]["selected_model"] == "ridge"
    assert "RidgeRegression" in h_map[24]["model_type"]

    # +48h should route to Ridge
    assert h_map[48]["selected_model"] == "ridge"
    assert "RidgeRegression" in h_map[48]["model_type"]

    # +72h should route to Persistence
    assert h_map[72]["selected_model"] == "persistence"
    assert "Persistence" in h_map[72]["model_type"]


def test_validation_selected_model_routing_igi_airport(client: TestClient) -> None:
    """
    Verify IGI Airport T3 validation model routing:
    +24h -> Persistence
    +48h -> Ridge (alpha=100)
    +72h -> Ridge (alpha=500)
    """
    ref_time = "2024-12-15T12:00:00Z"
    resp = client.get(f"/api/forecast/experimental?station_id=igi-airport-t3&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()
    h_map = {h["horizon_hours"]: h for h in data["horizons"]}

    assert h_map[24]["selected_model"] == "persistence"
    assert h_map[48]["selected_model"] == "ridge"
    assert h_map[72]["selected_model"] == "ridge"


def test_persistence_prediction_matches_anchor_value(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Verify that when Persistence is selected (+72h for Anand Vihar),
    the predicted value matches the PM2.5 observation at anchor t_0.
    """
    ref_time = "2024-12-15T12:00:00Z"
    t_0 = datetime.fromisoformat(ref_time.replace("Z", "+00:00"))

    # Query DB for anchor observation
    record = (
        db_session.query(ModeledAirQualityEstimate)
        .filter(
            ModeledAirQualityEstimate.station_id == "anand-vihar",
            ModeledAirQualityEstimate.valid_time == t_0,
        )
        .first()
    )
    assert record is not None
    assert record.pm2_5 is not None

    resp = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()
    h72 = next(h for h in data["horizons"] if h["horizon_hours"] == 72)
    assert h72["selected_model"] == "persistence"
    assert h72["predicted_pm2_5"] == round(float(record.pm2_5), 2)


# ---------------------------------------------------------------------------
# 3. Stale Data Rejection
# ---------------------------------------------------------------------------
def test_stale_data_rejection_low_threshold(client: TestClient) -> None:
    """Verify endpoint rejects request when data age exceeds max_staleness_hours threshold."""
    future_now = datetime.now(timezone.utc) + timedelta(hours=48)
    with patch("app.services.experimental_inference.datetime") as mock_dt:
        mock_dt.now.return_value = future_now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        resp = client.get("/api/forecast/experimental?station_id=anand-vihar&max_staleness_hours=24")
        assert resp.status_code == 503
        err = resp.json()["detail"]
        assert err["error"] == "StaleDataError"
        assert "freshness limit is 24h" in err["message"]
        assert "latest_available_utc" in err
        assert "staleness_hours" in err


def test_stale_historical_data_rejected_without_recent_records(
    db_session: Session,
) -> None:
    """
    Verify that if a station has only 2024 historical records (no recent 2026 data),
    live inference request returns 503 StaleDataError and never silently serves 2024 as 2026.
    """
    from fastapi import HTTPException
    # Mock latest row to return a 2024 record
    fake_row = MagicMock()
    fake_row.valid_time = datetime(2024, 12, 29, 23, 0, tzinfo=timezone.utc)

    with patch.object(db_session, "query") as mock_query:
        mock_filter = MagicMock()
        mock_query.return_value.filter.return_value.order_by.return_value.first.return_value = fake_row

        with pytest.raises(HTTPException) as exc_info:
            generate_experimental_forecast(
                db=db_session,
                station_id="anand-vihar",
                reference_time=None,  # Live inference mode
                max_staleness_hours=24,
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"] == "StaleDataError"
        assert "2024 reanalysis data cannot be served" in exc_info.value.detail["message"]


# ---------------------------------------------------------------------------
# 4. Missing / Insufficient History Rejection
# ---------------------------------------------------------------------------
def test_insufficient_history_rejection_early_in_dataset(client: TestClient) -> None:
    """
    Point-in-time anchor on Oct 2, 2024 has only 24 hours of preceding history,
    not the required 72 hours. Must return 503 InsufficientHistoryError.
    """
    early_ref_time = "2024-10-02T00:00:00Z"
    resp = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={early_ref_time}")
    assert resp.status_code == 503
    err = resp.json()["detail"]
    assert err["error"] == "InsufficientHistoryError"
    assert "missing_lag_hours" in err or "available_records" in err


def test_missing_history_completely_absent(client: TestClient) -> None:
    """Querying an era with zero data must return 503."""
    nonexistent_time = "2020-01-01T00:00:00Z"
    resp = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={nonexistent_time}")
    assert resp.status_code == 503
    err = resp.json()["detail"]
    assert err["error"] == "InsufficientHistoryError"


# ---------------------------------------------------------------------------
# 5. Feature Schema Mismatch Rejection
# ---------------------------------------------------------------------------
def test_feature_schema_mismatch_rejection(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """
    If metadata contains fewer or corrupted feature names, verify 503 FeatureSchemaMismatch.
    """
    from fastapi import HTTPException
    # Create corrupted metadata in tmp_path
    st_dir = tmp_path / "anand-vihar" / "pm2_5_h24"
    st_dir.mkdir(parents=True)
    corrupted_meta = {
        "station_id": "anand-vihar",
        "target_pollutant": "pm2_5",
        "forecast_horizon": 24,
        "feature_names": ["co_current", "pm2_5_current"],  # Only 2 features instead of 44!
        "model_selection": {"selected_model": "ridge"},
    }
    with open(st_dir / "metadata.json", "w") as f:
        json.dump(corrupted_meta, f)

    with pytest.raises(HTTPException) as exc_info:
        generate_experimental_forecast(
            db=db_session,
            station_id="anand-vihar",
            reference_time=datetime(2024, 12, 15, 12, 0, tzinfo=timezone.utc),
            artifacts_base_dir=str(tmp_path),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "FeatureSchemaMismatch"


# ---------------------------------------------------------------------------
# 6. Artifact Load Failure
# ---------------------------------------------------------------------------
def test_artifact_binary_missing_rejection(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """
    If metadata exists and specifies Ridge, but model.joblib is absent,
    verify structured 503 ModelArtifactUnavailable.
    """
    from fastapi import HTTPException
    # Copy valid metadata but omit model.joblib
    src_meta = Path(DEFAULT_ARTIFACT_DIR) / "anand-vihar" / "pm2_5_h24" / "metadata.json"
    st_dir = tmp_path / "anand-vihar" / "pm2_5_h24"
    st_dir.mkdir(parents=True)
    with open(src_meta) as f:
        valid_meta = json.load(f)
    with open(st_dir / "metadata.json", "w") as f:
        json.dump(valid_meta, f)

    with pytest.raises(HTTPException) as exc_info:
        generate_experimental_forecast(
            db=db_session,
            station_id="anand-vihar",
            reference_time=datetime(2024, 12, 15, 12, 0, tzinfo=timezone.utc),
            artifacts_base_dir=str(tmp_path),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "ModelArtifactUnavailable"


# ---------------------------------------------------------------------------
# 7. Unsupported Station 404
# ---------------------------------------------------------------------------
def test_unsupported_station_returns_404(client: TestClient) -> None:
    """Invalid station must return 404 Not Found with list of supported station IDs."""
    resp = client.get("/api/forecast/experimental?station_id=nonexistent-station-999")
    assert resp.status_code == 404
    err = resp.json()["detail"]
    assert err["error"] == "StationNotFound"
    assert "supported_station_ids" in err
    assert "anand-vihar" in err["supported_station_ids"]


# ---------------------------------------------------------------------------
# 8. Anti-Leakage / Zero Future Lookahead
# ---------------------------------------------------------------------------
def test_zero_future_lookahead_guarantee(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Verify that inserting a future record at t_0 + 1h with extreme PM2.5 (e.g. 9999.0)
    has ZERO effect on the forecast generated at reference time t_0.
    """
    ref_time = "2024-12-15T12:00:00Z"
    t_0 = datetime.fromisoformat(ref_time.replace("Z", "+00:00"))
    t_future = t_0 + timedelta(hours=1)

    # 1. Run baseline prediction at t_0
    resp_before = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={ref_time}")
    assert resp_before.status_code == 200
    preds_before = [h["predicted_pm2_5"] for h in resp_before.json()["horizons"]]

    # 2. Temporarily inject extreme future reading at t_0 + 1h
    # Note: DB already has regular reading at t_0 + 1h, so we temporarily modify it and roll back
    future_row = (
        db_session.query(ModeledAirQualityEstimate)
        .filter(
            ModeledAirQualityEstimate.station_id == "anand-vihar",
            ModeledAirQualityEstimate.valid_time == t_future,
        )
        .first()
    )
    original_pm2_5 = future_row.pm2_5 if future_row else None
    if future_row:
        future_row.pm2_5 = 9999.9
        db_session.commit()

    try:
        # 3. Re-run prediction at t_0
        resp_after = client.get(f"/api/forecast/experimental?station_id=anand-vihar&reference_time={ref_time}")
        assert resp_after.status_code == 200
        preds_after = [h["predicted_pm2_5"] for h in resp_after.json()["horizons"]]

        # 4. Predictions must be completely identical (zero lookahead leakage)
        assert preds_before == preds_after

    finally:
        # Restore database state
        if future_row:
            future_row.pm2_5 = original_pm2_5
            db_session.commit()


# ---------------------------------------------------------------------------
# 9. Nonnegative Prediction Output
# ---------------------------------------------------------------------------
def test_nonnegative_prediction_clamping(
    db_session: Session,
) -> None:
    """Verify that if a model outputs a negative concentration, it is clamped to 0.0."""
    # Mock pipeline.predict to return negative value
    mock_pipeline = MagicMock()
    mock_pipeline.predict.return_value = [-42.5]

    with patch("app.services.experimental_inference._load_cached_pipeline", return_value=mock_pipeline):
        resp = generate_experimental_forecast(
            db=db_session,
            station_id="anand-vihar",
            reference_time=datetime(2024, 12, 15, 12, 0, tzinfo=timezone.utc),
        )

        h24 = next(h for h in resp.horizons if h.horizon_hours == 24)
        assert h24.selected_model == "ridge"
        assert h24.predicted_pm2_5 == 0.0  # Clamped to 0.0


# ---------------------------------------------------------------------------
# 10. Preservation of Existing Forecast API Behavior
# ---------------------------------------------------------------------------
def test_existing_synthetic_forecast_endpoint_preserved(client: TestClient) -> None:
    """Verify GET /api/forecast?station_id=anand-vihar continues functioning unchanged."""
    resp = client.get("/api/forecast?station_id=anand-vihar")
    assert resp.status_code == 200
    data = resp.json()

    assert data["data_mode"] == "synthetic_demo"
    assert "illustrative, deterministic, and unvalidated" in data["statement"]
    assert data["forecast_hours"] == 72
    assert len(data["forecast"]) == 72
    assert data["station"]["id"] == "anand-vihar"
