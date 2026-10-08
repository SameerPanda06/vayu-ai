"""
Experimental forecasting inference service for Vayu AI.

Serves validation-selected baseline models (Ridge Regression, Persistence, Horizon-Aligned Seasonal)
for +24h, +48h, and +72h PM2.5 forecasting without disrupting operational synthetic endpoints.

Integrity Guarantees:
- Strict UTC timestamp handling.
- Purely causal inference (zero future-target look-ahead leakage).
- Rejection of stale historical data when served in real-time mode.
- Rejection of incomplete lag histories (< 72 continuous hours).
- Nonnegative clamping (max(0.0, y_hat)).
- Safe model artifact loading with path-traversal safeguards.
- No dynamic training inside API request cycle.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ModeledAirQualityEstimate
from app.schemas import ExperimentalForecastResponse, ExperimentalHorizonForecast
from app.services.dataset_builder import (
    AirQualityDataset,
    DatasetQualityReport,
    DatasetRecord,
    ensure_utc,
    truncate_to_hour,
)
from app.services.forecasting_features import (
    AUTOREGRESSIVE_LAGS,
    DEFAULT_HORIZONS,
    generate_forecasting_features,
)
from app.stations import get_all_stations, get_station_by_id

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_DIR = "artifacts/models"
REQUIRED_LAG_HOURS = 72
REQUIRED_WINDOW_STEPS = REQUIRED_LAG_HOURS + 1  # 73 hourly points [t_0 - 72h, t_0]

# In-memory artifact cache to avoid repeated disk reads during inference
_MODEL_CACHE: Dict[str, Tuple[float, Any]] = {}


def _get_safe_artifact_dir(
    station_id: str,
    horizon: int,
    base_dir: str = DEFAULT_ARTIFACT_DIR,
) -> Path:
    """
    Resolve and validate model artifact directory, preventing directory traversal.
    """
    base_path = Path(base_dir).resolve()
    target_path = (base_path / station_id / f"pm2_5_h{horizon}").resolve()

    if not str(target_path).startswith(str(base_path)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "InvalidPath", "message": "Invalid artifact path resolution."},
        )
    return target_path


def _load_cached_pipeline(model_path: Path) -> Any:
    """Load scikit-learn pipeline with mtime invalidation cache."""
    if not model_path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "ModelArtifactUnavailable",
                "message": f"Model binary artifact not found at {model_path.name}.",
            },
        )

    try:
        mtime = model_path.stat().st_mtime
        cache_key = str(model_path)
        if cache_key in _MODEL_CACHE:
            cached_mtime, pipeline = _MODEL_CACHE[cache_key]
            if cached_mtime == mtime:
                return pipeline

        pipeline = joblib.load(model_path)
        _MODEL_CACHE[cache_key] = (mtime, pipeline)
        return pipeline
    except Exception as exc:
        logger.error("Failed to load model artifact at %s: %s", model_path, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "ModelArtifactLoadFailure",
                "message": f"Failed to load trained pipeline: {str(exc)}",
            },
        )


def _load_validated_metadata(
    station_id: str,
    horizon: int,
    artifact_dir: Path,
) -> Dict[str, Any]:
    """
    Read and validate metadata.json for the specified station and horizon.
    Verifies station, pollutant, horizon, feature count, and validation selection.
    """
    metadata_path = artifact_dir / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "ModelArtifactUnavailable",
                "message": f"Audit metadata not found for station '{station_id}' at horizon +{horizon}h.",
            },
        )

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "CorruptedMetadata",
                "message": f"Could not read metadata for horizon +{horizon}h: {str(exc)}",
            },
        )

    # Integrity verification
    if meta.get("station_id") != station_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "MetadataMismatch",
                "message": f"Metadata station '{meta.get('station_id')}' does not match requested '{station_id}'.",
            },
        )

    if meta.get("target_pollutant") != "pm2_5":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "MetadataMismatch",
                "message": f"Metadata target pollutant is '{meta.get('target_pollutant')}', expected 'pm2_5'.",
            },
        )

    if meta.get("forecast_horizon") != horizon:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "MetadataMismatch",
                "message": f"Metadata horizon {meta.get('forecast_horizon')} does not match expected {horizon}.",
            },
        )

    feature_names = meta.get("feature_names")
    if not isinstance(feature_names, list) or len(feature_names) != 44:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "FeatureSchemaMismatch",
                "message": f"Expected 44 feature names in metadata, found {len(feature_names) if isinstance(feature_names, list) else 0}.",
            },
        )

    model_sel = meta.get("model_selection", {})
    if not model_sel.get("selected_model"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "ModelSelectionMissing",
                "message": f"No validation-selected model defined in metadata for horizon +{horizon}h.",
            },
        )

    return meta


def generate_experimental_forecast(
    db: Session,
    station_id: str,
    reference_time: Optional[datetime] = None,
    max_staleness_hours: int = 24,
    artifacts_base_dir: str = DEFAULT_ARTIFACT_DIR,
) -> ExperimentalForecastResponse:
    """
    Generate point-in-time experimental PM2.5 forecasts for +24h, +48h, and +72h.

    Parameters:
    - db: Active SQLAlchemy session.
    - station_id: Valid Delhi NCR monitoring station identifier.
    - reference_time: Optional point-in-time UTC forecast anchor t_0.
      If omitted, determines t_0 from latest available data and enforces real-time freshness.
    - max_staleness_hours: Permissible age of data when reference_time is omitted (default 24h).
    - artifacts_base_dir: Configured root directory containing trained model artifacts.
    """
    normalized_id = station_id.strip().lower()
    station = get_station_by_id(normalized_id)

    if not station:
        supported_ids = [s.id for s in get_all_stations()]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "StationNotFound",
                "message": f"Station '{station_id}' is not recognized in Delhi NCR network.",
                "supported_station_ids": supported_ids,
            },
        )

    # 1. Determine anchor timestamp t_0 and enforce freshness requirements
    if reference_time is None:
        now_utc = datetime.now(timezone.utc)
        # In Open-Meteo, hourly timestamps denote the beginning of the interval [t, t+1h).
        # An interval is only completed when reference time >= t + 1 hour.
        # Therefore, the latest completed interval start timestamp is:
        # truncate_to_hour(now_utc) - 1 hour.
        latest_completed_utc = truncate_to_hour(now_utc) - timedelta(hours=1)
        latest_row = (
            db.query(ModeledAirQualityEstimate)
            .filter(
                ModeledAirQualityEstimate.station_id == normalized_id,
                ModeledAirQualityEstimate.valid_time <= latest_completed_utc,
            )
            .order_by(ModeledAirQualityEstimate.valid_time.desc())
            .first()
        )

        if not latest_row:
            any_row = (
                db.query(ModeledAirQualityEstimate.id)
                .filter(ModeledAirQualityEstimate.station_id == normalized_id)
                .first()
            )
            if not any_row:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": "InsufficientData",
                        "message": f"No modeled atmospheric data available for station '{normalized_id}'.",
                        "station_id": normalized_id,
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "IncompleteIntervalError",
                    "message": (
                        f"No completed hourly records available for station '{normalized_id}' "
                        f"on or before latest completed interval boundary ({latest_completed_utc.isoformat()})."
                    ),
                    "station_id": normalized_id,
                },
            )

        latest_utc = truncate_to_hour(ensure_utc(latest_row.valid_time))
        staleness_hours = (now_utc - latest_utc).total_seconds() / 3600.0

        if staleness_hours > max_staleness_hours:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "StaleDataError",
                    "message": (
                        f"Latest available modeled record for station '{normalized_id}' is from "
                        f"{latest_utc.isoformat()}, which is {staleness_hours:.1f} hours old "
                        f"(freshness limit is {max_staleness_hours}h). Models trained on 2024 reanalysis "
                        "data cannot be served as current real-time forecasts without fresh input data."
                    ),
                    "station_id": normalized_id,
                    "latest_available_utc": latest_utc.isoformat(),
                    "current_time_utc": now_utc.isoformat(),
                    "staleness_hours": round(staleness_hours, 2),
                },
            )
        t_0 = latest_utc
    else:
        t_0 = truncate_to_hour(ensure_utc(reference_time))

    # 2. Query strictly causal historical window: [t_0 - 72h, t_0]
    t_start = t_0 - timedelta(hours=REQUIRED_LAG_HOURS)
    t_end = t_0

    db_rows = (
        db.query(ModeledAirQualityEstimate)
        .filter(
            ModeledAirQualityEstimate.station_id == normalized_id,
            ModeledAirQualityEstimate.valid_time >= t_start,
            ModeledAirQualityEstimate.valid_time <= t_end,
        )
        .order_by(ModeledAirQualityEstimate.valid_time.asc())
        .all()
    )

    records_by_time: Dict[datetime, ModeledAirQualityEstimate] = {
        truncate_to_hour(ensure_utc(r.valid_time)): r for r in db_rows
    }

    # 3. Verify point-in-time completeness and lag availability
    # Check anchor t_0
    rec_0 = records_by_time.get(t_0)
    if rec_0 is None or rec_0.pm2_5 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "InsufficientHistoryError",
                "message": f"Target pollutant PM2.5 observation at anchor time {t_0.isoformat()} is missing for station '{normalized_id}'.",
                "station_id": normalized_id,
                "reference_time_utc": t_0.isoformat(),
            },
        )

    # Check required autoregressive lags: (1, 2, 3, 6, 12, 24, 48, 72)
    for lag in AUTOREGRESSIVE_LAGS:
        t_lag = t_0 - timedelta(hours=lag)
        rec_lag = records_by_time.get(t_lag)
        if rec_lag is None or rec_lag.pm2_5 is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "InsufficientHistoryError",
                    "message": (
                        f"Missing required PM2.5 lag at t - {lag}h ({t_lag.isoformat()}). "
                        f"Requires complete 72-hour continuous history leading up to {t_0.isoformat()}."
                    ),
                    "station_id": normalized_id,
                    "missing_lag_hours": lag,
                    "available_records_in_window": len(records_by_time),
                    "required_records_in_window": REQUIRED_WINDOW_STEPS,
                },
            )

    if len(records_by_time) < REQUIRED_WINDOW_STEPS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "InsufficientHistoryError",
                "message": (
                    f"Station '{normalized_id}' has {len(records_by_time)} of {REQUIRED_WINDOW_STEPS} "
                    f"required hourly records in the 72-hour lag window ending at {t_0.isoformat()}."
                ),
                "station_id": normalized_id,
                "available_records": len(records_by_time),
                "required_records": REQUIRED_WINDOW_STEPS,
            },
        )

    # 4. Construct causal DatasetRecord objects strictly bounded by t <= t_0
    dataset_records: List[DatasetRecord] = []
    for step in range(REQUIRED_WINDOW_STEPS):
        cur_t = t_start + timedelta(hours=step)
        row = records_by_time.get(cur_t)
        if row:
            dataset_records.append(
                DatasetRecord(
                    timestamp=cur_t,
                    station_id=normalized_id,
                    source="open_meteo",
                    pm2_5=row.pm2_5,
                    pm10=row.pm10,
                    no2=row.no2,
                    so2=row.so2,
                    co=row.co,
                    o3=row.o3,
                )
            )

    quality_rep = DatasetQualityReport(
        station_id=normalized_id,
        source="open_meteo",
        start_time=t_start,
        end_time=t_end,
        total_expected_hours=REQUIRED_WINDOW_STEPS,
        available_hours=len(dataset_records),
        missing_hours=0,
        completeness_pct=100.0,
        null_counts={},
    )
    dataset = AirQualityDataset(
        station_id=normalized_id,
        source="open_meteo",
        records=dataset_records,
        quality_report=quality_rep,
    )

    # 5. Extract causal features at reference anchor t_0 (no future leakage)
    sup_dataset = generate_forecasting_features(
        dataset=dataset,
        target_pollutant="pm2_5",
        horizons=DEFAULT_HORIZONS,
        require_all_targets=False,
    )

    sample_at_t0 = next((s for s in sup_dataset.samples if s.timestamp == t_0), None)
    if not sample_at_t0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "FeatureExtractionFailed",
                "message": f"Failed to compute causal feature vector at {t_0.isoformat()}.",
            },
        )

    # 6. Evaluate validation-selected models for each horizon (+24h, +48h, +72h)
    horizon_forecasts: List[ExperimentalHorizonForecast] = []

    for h in DEFAULT_HORIZONS:
        artifact_dir = _get_safe_artifact_dir(
            station_id=normalized_id,
            horizon=h,
            base_dir=artifacts_base_dir,
        )
        metadata = _load_validated_metadata(
            station_id=normalized_id,
            horizon=h,
            artifact_dir=artifact_dir,
        )

        model_selection = metadata.get("model_selection", {})
        selected_model = model_selection.get("selected_model", "persistence")
        expected_features = metadata.get("feature_names", [])

        # Verify feature schema compatibility
        missing_features = [f for f in expected_features if f not in sample_at_t0.features]
        if missing_features:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "FeatureSchemaMismatch",
                    "message": f"Features missing from inference sample at +{h}h: {missing_features[:5]}",
                },
            )

        # Dispatch prediction to validation-selected model
        if selected_model == "ridge":
            pipeline = _load_cached_pipeline(artifact_dir / "model.joblib")
            # Build ordered feature array of exact shape (1, 44)
            x_vals = [sample_at_t0.features[f_name] for f_name in expected_features]
            x_matrix = np.asarray(x_vals, dtype=float).reshape(1, -1)
            raw_prediction = float(pipeline.predict(x_matrix)[0])

            alpha = metadata.get("hyperparameters", {}).get("alpha", "tuned")
            model_type = f"RidgeRegression(alpha={alpha})"
            artifact_id = f"{normalized_id}_pm2_5_h{h}_ridge"
            val_mae = metadata.get("evaluation_metrics", {}).get("ridge_val", {}).get("mae")

        elif selected_model in ("persistence", "seasonal_aligned"):
            # For 24h multiples (24h, 48h, 72h), daily seasonal aligns with current observation t_0
            raw_prediction = float(sample_at_t0.features.get("pm2_5_current", 0.0))
            if selected_model == "persistence":
                model_type = "Persistence Baseline (y_hat = y(t_0))"
                artifact_id = f"{normalized_id}_pm2_5_h{h}_persistence"
                val_mae = metadata.get("evaluation_metrics", {}).get("persistence_val", {}).get("mae")
            else:
                model_type = "Horizon-Aligned Daily Seasonal (y_hat = y(t_0))"
                artifact_id = f"{normalized_id}_pm2_5_h{h}_seasonal_aligned"
                val_mae = metadata.get("evaluation_metrics", {}).get("seasonal_aligned_val", {}).get("mae")

        elif selected_model == "seasonal_naive_24h":
            raw_prediction = float(
                sample_at_t0.features.get("pm2_5_lag_24h", sample_at_t0.features.get("pm2_5_current", 0.0))
            )
            model_type = "Seasonal Naive (y_hat = y(t_0 - 24h))"
            artifact_id = f"{normalized_id}_pm2_5_h{h}_seasonal_naive_24h"
            val_mae = metadata.get("evaluation_metrics", {}).get("seasonal_naive_24h_val", {}).get("mae")

        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "UnsupportedModelSelection",
                    "message": f"Unsupported model '{selected_model}' in validation metadata.",
                },
            )

        # Enforce nonnegativity
        clamped_prediction = max(0.0, raw_prediction)
        target_time_utc = t_0 + timedelta(hours=h)

        horizon_forecasts.append(
            ExperimentalHorizonForecast(
                horizon_hours=h,
                horizon_label=f"+{h}h",
                target_time_utc=target_time_utc,
                predicted_pm2_5=round(clamped_prediction, 2),
                selected_model=selected_model,
                model_type=model_type,
                artifact_id=artifact_id,
                validation_mae=round(val_mae, 3) if val_mae is not None else None,
            )
        )

    return ExperimentalForecastResponse(
        status="experimental",
        is_experimental=True,
        station_id=station.id,
        station_name=station.name,
        prediction_time_utc=t_0,
        target_pollutant="pm2_5",
        units="µg/m³",
        forecast_structure="discrete_milestones_24h_48h_72h",
        hourly_sequence_note=(
            "Baseline models predict 3 discrete horizons (+24h, +48h, +72h). "
            "A full 72-step hourly series requires direct 72-head multi-output models or recursive neural autoregression."
        ),
        data_provider="Open-Meteo (Copernicus CAMS atmospheric composition)",
        data_product="CAMS Global Operational Forecast (live inference) & CAMS Global Reanalysis (training)",
        training_period={
            "start_utc": "2024-10-01T00:00:00Z",
            "end_utc": "2024-12-29T23:00:00Z",
        },
        disclaimer=(
            "Experimental ML baseline forecast derived from Open-Meteo Copernicus CAMS "
            "atmospheric models. These are NOT official CPCB ground observations "
            "and do NOT replace operational forecasts."
        ),
        horizons=horizon_forecasts,
    )
