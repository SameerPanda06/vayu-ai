"""
Baseline forecasting models and chronological evaluation engine for Vayu AI.

Supports:
- Model A: Persistence (latest observation at t_0)
- Model B: Seasonal Naive (diurnal t_0 - 24h, and optional weekly t_0 - 168h)
- Model C: Ridge Regression with scikit-learn Pipeline (SimpleImputer + StandardScaler + Ridge)
  fitted strictly on the chronological training partition.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from app.services.dataset_builder import AirQualityDataset, build_hourly_dataset
from app.services.forecasting_features import (
    DEFAULT_HORIZONS,
    SupervisedDataset,
    SupervisedSample,
    generate_forecasting_features,
)

logger = logging.getLogger(__name__)

# Grid of alpha regularization parameters for validation tuning
DEFAULT_RIDGE_ALPHAS: Tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 50.0, 100.0, 500.0, 1000.0)


@dataclass
class ForecastMetrics:
    """Standard evaluation metrics for a single model and horizon."""
    mae: float
    rmse: float
    r2: float
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mae": round(self.mae, 3),
            "rmse": round(self.rmse, 3),
            "r2": round(self.r2, 4),
            "sample_count": self.sample_count,
        }


def calculate_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> ForecastMetrics:
    """
    Calculate MAE, RMSE, and R² for predictions against ground-truth targets.

    Edge Cases:
    - Empty sequence: returns zeroes.
    - Single sample or zero target variance: R² defaults to 0.0 to prevent division by zero.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)

    n = len(y_t)
    if n == 0:
        return ForecastMetrics(mae=0.0, rmse=0.0, r2=0.0, sample_count=0)

    mae_val = float(mean_absolute_error(y_t, y_p))
    rmse_val = float(root_mean_squared_error(y_t, y_p))

    # R2 computation with variance guard
    ss_tot = float(np.sum((y_t - np.mean(y_t)) ** 2))
    if n < 2 or ss_tot < 1e-9:
        r2_val = 0.0
    else:
        ss_res = float(np.sum((y_t - y_p) ** 2))
        r2_val = float(1.0 - (ss_res / ss_tot))

    return ForecastMetrics(
        mae=mae_val,
        rmse=rmse_val,
        r2=r2_val,
        sample_count=n,
    )


class PersistenceBaseline:
    """
    Model A: Persistence Baseline.

    Predicts future concentrations using the latest available observation at prediction time t_0:
    y_pred(t_0 + h) = y(t_0)
    """

    def __init__(self, target_pollutant: str = "pm2_5"):
        self.target_pollutant = target_pollutant
        self.feature_key = f"{target_pollutant}_current"

    def predict_sample(self, sample: SupervisedSample) -> Optional[float]:
        val = sample.features.get(self.feature_key)
        if val is not None:
            return float(val)
        # Fallback to lag_1h if current is missing
        fallback = sample.features.get(f"{self.target_pollutant}_lag_1h")
        return float(fallback) if fallback is not None else None

    def predict(self, samples: Sequence[SupervisedSample]) -> np.ndarray:
        preds = [self.predict_sample(s) for s in samples]
        return np.asarray(preds, dtype=float)


class SeasonalNaiveBaseline:
    """
    Model B: Seasonal Naive Baseline (Fixed t - 24h lag).

    Predicts future concentrations using the observation from 24 hours prior to prediction time t_0:
    y_pred(t_0 + h) = y(t_0 - 24h)
    """

    def __init__(self, target_pollutant: str = "pm2_5", lag_hours: int = 24):
        self.target_pollutant = target_pollutant
        self.lag_hours = lag_hours
        self.feature_key = f"{target_pollutant}_lag_{lag_hours}h"

    def predict_sample(self, sample: SupervisedSample) -> Optional[float]:
        val = sample.features.get(self.feature_key)
        if val is not None:
            return float(val)
        # Fallback to current if lag is missing
        fallback = sample.features.get(f"{self.target_pollutant}_current")
        return float(fallback) if fallback is not None else None

    def predict(self, samples: Sequence[SupervisedSample]) -> np.ndarray:
        preds = [self.predict_sample(s) for s in samples]
        return np.asarray(preds, dtype=float)


class HorizonAlignedDailySeasonalBaseline:
    """
    Horizon-Aligned Daily Seasonal Baseline.

    Predicts future concentrations using the latest available observation at or before
    prediction time t_0 that shares the exact same hour-of-day as the forecast target (t_0 + h).

    Causal Formulation:
    - Target timestamp: t_target = t_0 + h
    - Target hour-of-day: H = (t_0 + h).hour
    - Latest past observation timestamp t <= t_0 with t.hour == H:
      lag_hours = (24 - (h % 24)) % 24
      t_latest = t_0 - lag_hours
    - For exact daily multiples (h in {24, 48, 72}):
      lag_hours = 0 -> predicts y(t_0) (coincides with latest observation / persistence).
    - For intraday horizons (e.g. h = 12):
      lag_hours = 12 -> predicts y(t_0 - 12h).
    """

    def __init__(self, horizon: int, target_pollutant: str = "pm2_5"):
        self.horizon = horizon
        self.target_pollutant = target_pollutant
        self.lag_hours = (24 - (horizon % 24)) % 24

    def predict_sample(self, sample: SupervisedSample) -> Optional[float]:
        if self.lag_hours == 0:
            val = sample.features.get(f"{self.target_pollutant}_current")
        else:
            val = sample.features.get(f"{self.target_pollutant}_lag_{self.lag_hours}h")
            if val is None:
                val = sample.features.get(f"{self.target_pollutant}_current")
        return float(val) if val is not None else None

    def predict(self, samples: Sequence[SupervisedSample]) -> np.ndarray:
        preds = [self.predict_sample(s) for s in samples]
        return np.asarray(preds, dtype=float)


class RidgeBaseline:
    """
    Model C: Horizon-specific Ridge Regression Baseline.

    Uses a scikit-learn Pipeline with:
    1. SimpleImputer (median strategy) to handle any missing co-pollutants or historical features.
    2. StandardScaler to normalize lag, rolling, and temporal features.
    3. Ridge linear regression with L2 regularization.

    Critical Integrity Guarantees:
    - Preprocessing and scaling are fitted STRICTLY on the training partition.
    - Validation and test partitions are transformed without fitting to prevent leakage.
    - Missing targets are NEVER imputed; samples missing the target horizon are filtered out.
    """

    def __init__(
        self,
        horizon: int,
        target_pollutant: str = "pm2_5",
        alpha: float = 1.0,
        feature_names: Optional[List[str]] = None,
    ):
        self.horizon = horizon
        self.target_pollutant = target_pollutant
        self.alpha = alpha
        self.feature_names = feature_names or []
        self.pipeline: Optional[Pipeline] = None

    def _create_pipeline(self, alpha: float) -> Pipeline:
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=alpha, random_state=42)),
            ]
        )

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "RidgeBaseline":
        self.pipeline = self._create_pipeline(self.alpha)
        self.pipeline.fit(X_train, y_train)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("Model has not been fitted. Call fit() before predict().")
        return self.pipeline.predict(X)

    @classmethod
    def tune_and_fit(
        cls,
        horizon: int,
        target_pollutant: str,
        feature_names: List[str],
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        candidate_alphas: Sequence[float] = DEFAULT_RIDGE_ALPHAS,
    ) -> Tuple["RidgeBaseline", float, Dict[float, float]]:
        """
        Evaluate candidate regularization alphas on validation partition and fit optimal model.
        Returns: (fitted_best_model, best_alpha, validation_mae_by_alpha)
        """
        if len(X_train) == 0 or len(y_train) == 0:
            raise ValueError("Training data is empty; cannot fit RidgeBaseline.")

        val_mae_map: Dict[float, float] = {}
        best_alpha = candidate_alphas[0]
        best_val_mae = float("inf")

        for alpha in candidate_alphas:
            candidate_model = cls(
                horizon=horizon,
                target_pollutant=target_pollutant,
                alpha=alpha,
                feature_names=feature_names,
            )
            candidate_model.fit(X_train, y_train)

            if len(X_val) > 0 and len(y_val) > 0:
                y_val_pred = candidate_model.predict(X_val)
                val_mae = float(mean_absolute_error(y_val, y_val_pred))
            else:
                val_mae = 0.0

            val_mae_map[alpha] = val_mae
            if val_mae < best_val_mae:
                best_val_mae = val_mae
                best_alpha = alpha

        # Refit best model
        best_model = cls(
            horizon=horizon,
            target_pollutant=target_pollutant,
            alpha=best_alpha,
            feature_names=feature_names,
        )
        best_model.fit(X_train, y_train)
        return best_model, best_alpha, val_mae_map


def extract_feature_matrix(
    samples: Sequence[SupervisedSample],
    feature_names: Sequence[str],
) -> np.ndarray:
    """Convert sample features dictionary into an ordered 2D NumPy array."""
    if not samples:
        return np.empty((0, len(feature_names)), dtype=float)

    matrix = np.full((len(samples), len(feature_names)), np.nan, dtype=float)
    for i, s in enumerate(samples):
        for j, feat in enumerate(feature_names):
            val = s.features.get(feat)
            if val is not None:
                matrix[i, j] = val
    return matrix


def filter_samples_for_horizon(
    samples: Sequence[SupervisedSample],
    target_pollutant: str,
    horizon: int,
) -> Tuple[List[SupervisedSample], np.ndarray]:
    """
    Filter samples that possess a valid non-null ground-truth target for horizon h.
    Returns: (filtered_samples, target_vector_y)
    """
    target_key = f"target_{target_pollutant}_h{horizon}"
    valid_samples: List[SupervisedSample] = []
    y_vals: List[float] = []

    for s in samples:
        val = s.targets.get(target_key)
        if val is not None and not math.isnan(val):
            valid_samples.append(s)
            y_vals.append(float(val))

    return valid_samples, np.asarray(y_vals, dtype=float)


@dataclass
class HorizonEvaluationResult:
    """Evaluation results across all baselines for a specific horizon."""
    horizon: int
    target_pollutant: str
    sample_count_train: int
    sample_count_val: int
    sample_count_test: int
    persistence_val: ForecastMetrics
    persistence_test: ForecastMetrics
    seasonal_naive_val: ForecastMetrics
    seasonal_naive_test: ForecastMetrics
    seasonal_aligned_val: ForecastMetrics
    seasonal_aligned_test: ForecastMetrics
    ridge_val: ForecastMetrics
    ridge_test: ForecastMetrics
    ridge_train: ForecastMetrics
    ridge_best_alpha: float
    ridge_model: RidgeBaseline
    selected_model_val: str  # Model selected strictly on Validation partition MAE
    best_model_test: str     # Post-hoc informational ranking on test set

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon": self.horizon,
            "horizon_label": f"+{self.horizon}h",
            "target_pollutant": self.target_pollutant,
            "sample_counts": {
                "train": self.sample_count_train,
                "val": self.sample_count_val,
                "test": self.sample_count_test,
            },
            "persistence": {
                "val": self.persistence_val.to_dict(),
                "test": self.persistence_test.to_dict(),
            },
            "seasonal_naive_24h": {
                "val": self.seasonal_naive_val.to_dict(),
                "test": self.seasonal_naive_test.to_dict(),
            },
            "seasonal_aligned": {
                "val": self.seasonal_aligned_val.to_dict(),
                "test": self.seasonal_aligned_test.to_dict(),
            },
            "ridge": {
                "best_alpha": self.ridge_best_alpha,
                "train": self.ridge_train.to_dict(),
                "val": self.ridge_val.to_dict(),
                "test": self.ridge_test.to_dict(),
            },
            "model_selection": {
                "selected_model_by_val": self.selected_model_val,
                "selection_criterion": "lowest_validation_mae",
            },
            "best_model_test": self.best_model_test,
        }


@dataclass
class StationEvaluationSummary:
    """Complete chronological baseline evaluation summary for a station."""
    station_id: str
    source_provider: str
    target_pollutant: str
    dataset_start_utc: str
    dataset_end_utc: str
    total_raw_records: int
    total_supervised_samples: int
    train_samples_raw: int
    val_samples_raw: int
    test_samples_raw: int
    embargo_gap_hours: int
    feature_count: int
    feature_names: List[str]
    horizon_results: Dict[int, HorizonEvaluationResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "station_id": self.station_id,
            "source_provider": self.source_provider,
            "target_pollutant": self.target_pollutant,
            "date_range": {
                "start_utc": self.dataset_start_utc,
                "end_utc": self.dataset_end_utc,
            },
            "counts": {
                "raw_records": self.total_raw_records,
                "total_supervised_samples": self.total_supervised_samples,
                "train_samples_raw": self.train_samples_raw,
                "val_samples_raw": self.val_samples_raw,
                "test_samples_raw": self.test_samples_raw,
                "embargo_gap_hours": self.embargo_gap_hours,
                "feature_count": self.feature_count,
            },
            "horizons": {
                f"+{h}h": res.to_dict() for h, res in self.horizon_results.items()
            },
        }


def evaluate_station_baselines(
    db: Session,
    station_id: str,
    start_time: datetime,
    end_time: datetime,
    target_pollutant: str = "pm2_5",
    horizons: Tuple[int, ...] = DEFAULT_HORIZONS,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    embargo_gap_hours: int = 72,
    candidate_alphas: Sequence[float] = DEFAULT_RIDGE_ALPHAS,
) -> StationEvaluationSummary:
    """
    Execute full chronological baseline training and evaluation for a station.

    Methodology:
    1. Extracts chronological hourly records from database (strictly Open-Meteo source).
    2. Generates backward-looking causal features and +24h, +48h, +72h future targets.
    3. Partitions samples into chronological Train (70%), Val (15%), Test (15%) splits
       with 72-hour temporal embargo gaps preventing target-overlap leakage.
    4. Evaluates Persistence and Seasonal Naive baselines.
    5. Tunes Ridge regression on Validation partition and evaluates on untouched Test partition.
    6. Identifies best-performing model on Test partition by lowest MAE.
    """
    clean_station = station_id.strip().lower()

    # 1. Build raw chronological dataset
    raw_dataset: AirQualityDataset = build_hourly_dataset(
        db=db,
        station_id=clean_station,
        start_time=start_time,
        end_time=end_time,
        source="open_meteo",
        pollutant=target_pollutant,
    )

    if not raw_dataset.records:
        raise ValueError(
            f"No Open-Meteo records found for station '{clean_station}' in range "
            f"{start_time.isoformat()} to {end_time.isoformat()}."
        )

    # 2. Generate causal feature dataset
    supervised_ds: SupervisedDataset = generate_forecasting_features(
        dataset=raw_dataset,
        target_pollutant=target_pollutant,
        horizons=horizons,
        require_all_targets=False,
    )

    # 3. Chronological train/val/test split with 72h embargo gap
    train_samples, val_samples, test_samples = supervised_ds.train_val_test_split(
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        embargo_gap_hours=embargo_gap_hours,
    )

    feature_names = supervised_ds.feature_names
    horizon_results: Dict[int, HorizonEvaluationResult] = {}

    model_persistence = PersistenceBaseline(target_pollutant=target_pollutant)
    model_seasonal = SeasonalNaiveBaseline(target_pollutant=target_pollutant, lag_hours=24)

    # 4. Evaluate each horizon independently
    for h in horizons:
        # Filter samples that have non-null target for this horizon
        tr_h, y_tr = filter_samples_for_horizon(train_samples, target_pollutant, h)
        val_h, y_val = filter_samples_for_horizon(val_samples, target_pollutant, h)
        te_h, y_te = filter_samples_for_horizon(test_samples, target_pollutant, h)

        if len(tr_h) == 0:
            raise ValueError(f"Station {clean_station}: No training samples with valid target for +{h}h.")
        if len(te_h) == 0:
            raise ValueError(f"Station {clean_station}: No test samples with valid target for +{h}h.")

        # Baseline A: Persistence
        pers_val_pred = model_persistence.predict(val_h)
        pers_te_pred = model_persistence.predict(te_h)
        pers_val_metrics = calculate_metrics(y_val, pers_val_pred)
        pers_te_metrics = calculate_metrics(y_te, pers_te_pred)

        # Baseline B: Seasonal Naive (t_0 - 24h)
        seas_val_pred = model_seasonal.predict(val_h)
        seas_te_pred = model_seasonal.predict(te_h)
        seas_val_metrics = calculate_metrics(y_val, seas_val_pred)
        seas_te_metrics = calculate_metrics(y_te, seas_te_pred)

        # Baseline B2: Horizon-Aligned Daily Seasonal
        model_aligned = HorizonAlignedDailySeasonalBaseline(horizon=h, target_pollutant=target_pollutant)
        aligned_val_pred = model_aligned.predict(val_h)
        aligned_te_pred = model_aligned.predict(te_h)
        aligned_val_metrics = calculate_metrics(y_val, aligned_val_pred)
        aligned_te_metrics = calculate_metrics(y_te, aligned_te_pred)

        # Baseline C: Ridge Regression
        X_tr = extract_feature_matrix(tr_h, feature_names)
        X_val = extract_feature_matrix(val_h, feature_names)
        X_te = extract_feature_matrix(te_h, feature_names)

        best_ridge_model, best_alpha, _ = RidgeBaseline.tune_and_fit(
            horizon=h,
            target_pollutant=target_pollutant,
            feature_names=feature_names,
            X_train=X_tr,
            y_train=y_tr,
            X_val=X_val,
            y_val=y_val,
            candidate_alphas=candidate_alphas,
        )

        ridge_tr_pred = best_ridge_model.predict(X_tr)
        ridge_val_pred = best_ridge_model.predict(X_val)
        ridge_te_pred = best_ridge_model.predict(X_te)

        ridge_tr_metrics = calculate_metrics(y_tr, ridge_tr_pred)
        ridge_val_metrics = calculate_metrics(y_val, ridge_val_pred)
        ridge_te_metrics = calculate_metrics(y_te, ridge_te_pred)

        # Model selection decision: STRICTLY based on Validation partition MAE
        # The test partition is NEVER used to choose the model.
        val_candidates = [
            ("persistence", pers_val_metrics.mae),
            ("seasonal_naive_24h", seas_val_metrics.mae),
            ("seasonal_aligned", aligned_val_metrics.mae),
            ("ridge", ridge_val_metrics.mae),
        ]
        val_candidates.sort(key=lambda item: item[1])
        selected_model_val = val_candidates[0][0]

        # Post-hoc informational ranking on untouched test partition
        test_candidates = [
            ("persistence", pers_te_metrics.mae),
            ("seasonal_naive_24h", seas_te_metrics.mae),
            ("seasonal_aligned", aligned_te_metrics.mae),
            ("ridge", ridge_te_metrics.mae),
        ]
        test_candidates.sort(key=lambda item: item[1])
        best_model_test = test_candidates[0][0]

        horizon_results[h] = HorizonEvaluationResult(
            horizon=h,
            target_pollutant=target_pollutant,
            sample_count_train=len(tr_h),
            sample_count_val=len(val_h),
            sample_count_test=len(te_h),
            persistence_val=pers_val_metrics,
            persistence_test=pers_te_metrics,
            seasonal_naive_val=seas_val_metrics,
            seasonal_naive_test=seas_te_metrics,
            seasonal_aligned_val=aligned_val_metrics,
            seasonal_aligned_test=aligned_te_metrics,
            ridge_val=ridge_val_metrics,
            ridge_test=ridge_te_metrics,
            ridge_train=ridge_tr_metrics,
            ridge_best_alpha=best_alpha,
            ridge_model=best_ridge_model,
            selected_model_val=selected_model_val,
            best_model_test=best_model_test,
        )

    return StationEvaluationSummary(
        station_id=clean_station,
        source_provider="Open-Meteo (modeled/reanalysis)",
        target_pollutant=target_pollutant,
        dataset_start_utc=raw_dataset.quality_report.start_time.isoformat(),
        dataset_end_utc=raw_dataset.quality_report.end_time.isoformat(),
        total_raw_records=len(raw_dataset.records),
        total_supervised_samples=len(supervised_ds.samples),
        train_samples_raw=len(train_samples),
        val_samples_raw=len(val_samples),
        test_samples_raw=len(test_samples),
        embargo_gap_hours=embargo_gap_hours,
        feature_count=len(feature_names),
        feature_names=feature_names,
        horizon_results=horizon_results,
    )
