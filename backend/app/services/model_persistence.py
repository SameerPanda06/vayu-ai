"""
Model artifact management and serialization service for Vayu AI baselines.

Persists trained model pipelines and complete audit metadata to local storage
under dedicated, git-ignored artifact directories.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
from sklearn.pipeline import Pipeline

from app.services.baselines import (
    HorizonEvaluationResult,
    RidgeBaseline,
    StationEvaluationSummary,
)

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_DIR = "artifacts/models"


def get_artifact_directory(base_dir: Optional[str] = None) -> Path:
    """Return resolved Path to the models artifact directory, creating it if needed."""
    path = Path(base_dir or DEFAULT_ARTIFACT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_horizon_model_artifact(
    station_summary: StationEvaluationSummary,
    horizon_result: HorizonEvaluationResult,
    output_base_dir: Optional[str] = None,
) -> Path:
    """
    Save a single horizon Ridge model pipeline (.joblib) and detailed audit metadata (.json).

    Metadata includes:
    - Station ID & Target pollutant
    - Forecast horizon (+24h, +48h, +72h)
    - Model type & hyperparameters (alpha)
    - Training date range
    - Feature names and ordering
    - Data provider provenance and disclaimers
    - Complete evaluation metrics across train/val/test partitions
    - Training timestamp
    """
    base_path = get_artifact_directory(output_base_dir)
    target_dir = base_path / station_summary.station_id / f"{station_summary.target_pollutant}_h{horizon_result.horizon}"
    target_dir.mkdir(parents=True, exist_ok=True)

    model_path = target_dir / "model.joblib"
    metadata_path = target_dir / "metadata.json"

    # 1. Save scikit-learn pipeline
    if horizon_result.ridge_model.pipeline is None:
        raise ValueError("Cannot persist unfitted pipeline.")
    joblib.dump(horizon_result.ridge_model.pipeline, model_path)

    # 2. Build metadata dictionary
    metadata: Dict[str, Any] = {
        "station_id": station_summary.station_id,
        "target_pollutant": station_summary.target_pollutant,
        "forecast_horizon": horizon_result.horizon,
        "horizon_label": f"+{horizon_result.horizon}h",
        "model_type": "RidgeRegression",
        "data_provider": station_summary.source_provider,
        "provenance_disclaimer": (
            "Evaluated against Open-Meteo modeled/reanalysis concentrations, "
            "NOT official CPCB ground observations."
        ),
        "training_date_range": {
            "start_utc": station_summary.dataset_start_utc,
            "end_utc": station_summary.dataset_end_utc,
        },
        "hyperparameters": {
            "alpha": horizon_result.ridge_best_alpha,
            "fit_intercept": True,
            "imputer_strategy": "median",
            "scaler": "StandardScaler",
        },
        "feature_count": station_summary.feature_count,
        "feature_names": station_summary.feature_names,
        "sample_counts": {
            "raw_records": station_summary.total_raw_records,
            "train": horizon_result.sample_count_train,
            "val": horizon_result.sample_count_val,
            "test": horizon_result.sample_count_test,
            "embargo_gap_hours": station_summary.embargo_gap_hours,
        },
        "evaluation_metrics": {
            "ridge_train": horizon_result.ridge_train.to_dict(),
            "ridge_val": horizon_result.ridge_val.to_dict(),
            "ridge_test": horizon_result.ridge_test.to_dict(),
            "persistence_val": horizon_result.persistence_val.to_dict(),
            "persistence_test": horizon_result.persistence_test.to_dict(),
            "seasonal_naive_24h_val": horizon_result.seasonal_naive_val.to_dict(),
            "seasonal_naive_24h_test": horizon_result.seasonal_naive_test.to_dict(),
            "seasonal_aligned_val": horizon_result.seasonal_aligned_val.to_dict(),
            "seasonal_aligned_test": horizon_result.seasonal_aligned_test.to_dict(),
        },
        "model_selection": {
            "decision_partition": "validation",
            "selection_criterion": "lowest_validation_mae",
            "selected_model": horizon_result.selected_model_val,
            "test_partition_status": "held_out_for_unbiased_evaluation_only",
        },
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "files": {
            "model_file": model_path.name,
            "metadata_file": metadata_path.name,
        },
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Saved model artifact to %s", target_dir)
    return target_dir


def save_station_artifacts(
    station_summary: StationEvaluationSummary,
    output_base_dir: Optional[str] = None,
) -> List[Path]:
    """Save model artifacts and metadata for all horizons of a station."""
    saved_dirs: List[Path] = []
    for horizon, horizon_res in station_summary.horizon_results.items():
        dir_path = save_horizon_model_artifact(
            station_summary=station_summary,
            horizon_result=horizon_res,
            output_base_dir=output_base_dir,
        )
        saved_dirs.append(dir_path)
    return saved_dirs


def load_model_artifact(artifact_dir: str | Path) -> Tuple[RidgeBaseline, Dict[str, Any]]:
    """
    Load a persisted model pipeline and its audit metadata from an artifact directory.
    Returns: (reconstructed_ridge_baseline, metadata_dict)
    """
    path = Path(artifact_dir)
    model_path = path / "model.joblib"
    metadata_path = path / "metadata.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found at {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pipeline: Pipeline = joblib.load(model_path)

    baseline = RidgeBaseline(
        horizon=metadata["forecast_horizon"],
        target_pollutant=metadata["target_pollutant"],
        alpha=metadata["hyperparameters"]["alpha"],
        feature_names=metadata["feature_names"],
    )
    baseline.pipeline = pipeline

    return baseline, metadata


def list_saved_artifacts(base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scan artifact directory and return metadata summaries of all saved models."""
    base_path = Path(base_dir or DEFAULT_ARTIFACT_DIR)
    if not base_path.exists():
        return []

    summaries: List[Dict[str, Any]] = []
    for meta_file in sorted(base_path.glob("*/*/metadata.json")):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                summaries.append({
                    "station_id": data.get("station_id"),
                    "pollutant": data.get("target_pollutant"),
                    "horizon": data.get("forecast_horizon"),
                    "path": str(meta_file.parent),
                    "best_alpha": data.get("hyperparameters", {}).get("alpha"),
                    "test_mae": data.get("evaluation_metrics", {}).get("ridge_test", {}).get("mae"),
                    "training_timestamp": data.get("training_timestamp"),
                })
        except Exception as e:
            logger.warning("Could not read artifact metadata at %s: %s", meta_file, e)

    return summaries
