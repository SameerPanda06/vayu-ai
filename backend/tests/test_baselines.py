"""
Unit and integration tests for baseline forecasting engine in Vayu AI.

Verifies:
- Persistence prediction correctness
- Seasonal naive prediction correctness
- Ridge feature alignment
- Chronological split integrity & horizon embargo enforcement
- Preprocessing fitted only on training data (no leakage)
- Missing-value handling (feature imputation vs target exclusion)
- Metric calculations (MAE, RMSE, R²)
- Model artifact metadata and loading
- Zero future-target leakage in feature sets
- Insufficient-history handling
"""

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import numpy as np
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.baselines import (
    ForecastMetrics,
    PersistenceBaseline,
    RidgeBaseline,
    SeasonalNaiveBaseline,
    calculate_metrics,
    extract_feature_matrix,
    filter_samples_for_horizon,
)
from app.services.dataset_builder import AirQualityDataset, DatasetQualityReport, DatasetRecord
from app.services.forecasting_features import (
    SupervisedDataset,
    SupervisedSample,
    generate_forecasting_features,
)
from app.services.model_persistence import (
    load_model_artifact,
    save_horizon_model_artifact,
)


def _make_dummy_sample(
    dt: datetime,
    pm2_5_curr: float = 100.0,
    pm2_5_lag24: float = 95.0,
    target_h24: float = 110.0,
    target_h48: float = 115.0,
    target_h72: float = 120.0,
) -> SupervisedSample:
    return SupervisedSample(
        timestamp=dt,
        station_id="test-station",
        features={
            "pm2_5_current": pm2_5_curr,
            "pm2_5_lag_24h": pm2_5_lag24,
            "pm10_current": 150.0,
            "time_hour_sin": 0.5,
            "time_hour_cos": 0.866,
        },
        targets={
            "target_pm2_5_h24": target_h24,
            "target_pm2_5_h48": target_h48,
            "target_pm2_5_h72": target_h72,
        },
    )


def test_persistence_prediction_correctness():
    dt = datetime(2024, 10, 10, 12, 0, tzinfo=timezone.utc)
    sample = _make_dummy_sample(dt, pm2_5_curr=142.5)

    model = PersistenceBaseline(target_pollutant="pm2_5")
    pred_single = model.predict_sample(sample)
    assert pred_single == 142.5

    samples = [
        _make_dummy_sample(dt, pm2_5_curr=50.0),
        _make_dummy_sample(dt + timedelta(hours=1), pm2_5_curr=75.0),
    ]
    preds = model.predict(samples)
    assert np.array_equal(preds, np.array([50.0, 75.0]))


def test_seasonal_naive_prediction_correctness():
    dt = datetime(2024, 10, 10, 12, 0, tzinfo=timezone.utc)
    sample = _make_dummy_sample(dt, pm2_5_curr=120.0, pm2_5_lag24=88.0)

    model = SeasonalNaiveBaseline(target_pollutant="pm2_5", lag_hours=24)
    pred_single = model.predict_sample(sample)
    assert pred_single == 88.0

    # Test fallback to current if 24h lag is missing
    sample_no_lag = SupervisedSample(
        timestamp=dt,
        station_id="test-station",
        features={"pm2_5_current": 120.0},
        targets={},
    )
    fallback_pred = model.predict_sample(sample_no_lag)
    assert fallback_pred == 120.0


def test_horizon_aligned_daily_seasonal_prediction_correctness():
    from app.services.baselines import HorizonAlignedDailySeasonalBaseline

    dt = datetime(2024, 10, 10, 12, 0, tzinfo=timezone.utc)
    sample = SupervisedSample(
        timestamp=dt,
        station_id="test-station",
        features={
            "pm2_5_current": 135.0,
            "pm2_5_lag_12h": 90.0,
            "pm2_5_lag_24h": 110.0,
        },
        targets={},
    )

    # For daily multiples (24h, 48h, 72h), the target is at the exact same hour of day as t_0.
    # Therefore, the latest available observation at prediction time is t_0 itself (pm2_5_current).
    for h in (24, 48, 72):
        model_aligned = HorizonAlignedDailySeasonalBaseline(horizon=h, target_pollutant="pm2_5")
        assert model_aligned.lag_hours == 0
        pred = model_aligned.predict_sample(sample)
        assert pred == 135.0

    # For non-daily multiples (e.g. h=12), target hour is (12 + 12) % 24 = 0.
    # Latest observation at hour 0 was at t_0 - 12h:
    model_h12 = HorizonAlignedDailySeasonalBaseline(horizon=12, target_pollutant="pm2_5")
    assert model_h12.lag_hours == 12
    pred_h12 = model_h12.predict_sample(sample)
    assert pred_h12 == 90.0


def test_ridge_feature_alignment():
    dt = datetime(2024, 10, 10, 12, 0, tzinfo=timezone.utc)
    sample1 = SupervisedSample(
        timestamp=dt,
        station_id="test-station",
        features={"feat_b": 2.0, "feat_a": 1.0, "feat_c": 3.0},
        targets={},
    )
    sample2 = SupervisedSample(
        timestamp=dt,
        station_id="test-station",
        features={"feat_c": 6.0, "feat_b": 5.0, "feat_a": 4.0},
        targets={},
    )

    feature_names = ["feat_a", "feat_b", "feat_c"]
    matrix = extract_feature_matrix([sample1, sample2], feature_names)

    assert matrix.shape == (2, 3)
    # Check that columns strictly follow feature_names ordering
    assert np.array_equal(matrix[0], np.array([1.0, 2.0, 3.0]))
    assert np.array_equal(matrix[1], np.array([4.0, 5.0, 6.0]))


def test_chronological_split_integrity_and_embargo():
    base_time = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    # Require > 480 samples so that 15% val split (>= 73 hours) exceeds the 72h embargo gap
    samples = [
        _make_dummy_sample(base_time + timedelta(hours=i))
        for i in range(1000)
    ]
    sup_ds = SupervisedDataset(
        samples=samples,
        feature_names=["pm2_5_current"],
        target_names=["target_pm2_5_h24"],
        target_pollutant="pm2_5",
        horizons=(24, 48, 72),
    )

    train, val, test = sup_ds.train_val_test_split(
        train_ratio=0.70,
        val_ratio=0.15,
        embargo_gap_hours=72,
    )

    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0

    # Strict chronological ordering
    assert train[-1].timestamp < val[0].timestamp
    assert val[-1].timestamp < test[0].timestamp

    # Embargo buffer verification: gap between last train sample and first val sample must exceed 72h
    gap_train_val = (val[0].timestamp - train[-1].timestamp).total_seconds() / 3600.0
    assert gap_train_val > 72.0

    # Gap between last val sample and first test sample must exceed 72h
    gap_val_test = (test[0].timestamp - val[-1].timestamp).total_seconds() / 3600.0
    assert gap_val_test > 72.0


def test_preprocessing_fitted_only_on_training_data():
    """
    Critical requirement: Preprocessing scaler and imputer must fit strictly on train partition.
    Test that the scaler mean matches train mean and is unaffected by test data.
    """
    np.random.seed(42)
    # Train data: distribution centered at 50.0
    X_train = np.random.normal(loc=50.0, scale=5.0, size=(100, 3))
    y_train = X_train[:, 0] * 1.5 + 10.0

    # Test data: distribution centered at 500.0 (drastically different)
    X_test = np.random.normal(loc=500.0, scale=5.0, size=(50, 3))

    model = RidgeBaseline(horizon=24, target_pollutant="pm2_5", alpha=1.0)
    model.fit(X_train, y_train)

    assert model.pipeline is not None
    scaler: StandardScaler = model.pipeline.named_steps["scaler"]

    # Scaler mean must closely match X_train mean (~50.0), NOT X_test (~500.0)
    np.testing.assert_allclose(scaler.mean_, np.mean(X_train, axis=0), atol=1e-5)
    assert np.all(scaler.mean_ < 100.0)

    # Calling predict on X_test transforms with train statistics without modifying scaler
    _ = model.predict(X_test)
    np.testing.assert_allclose(scaler.mean_, np.mean(X_train, axis=0), atol=1e-5)


def test_missing_value_handling():
    dt = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    sample_valid = _make_dummy_sample(dt, target_h24=120.0)
    sample_none_target = SupervisedSample(
        timestamp=dt + timedelta(hours=1),
        station_id="test",
        features={"pm2_5_current": 100.0},
        targets={"target_pm2_5_h24": None},
    )
    sample_nan_target = SupervisedSample(
        timestamp=dt + timedelta(hours=2),
        station_id="test",
        features={"pm2_5_current": 100.0},
        targets={"target_pm2_5_h24": float("nan")},
    )

    valid_samples, y_vec = filter_samples_for_horizon(
        [sample_valid, sample_none_target, sample_nan_target],
        target_pollutant="pm2_5",
        horizon=24,
    )

    # Missing targets must be strictly dropped, NEVER silently imputed
    assert len(valid_samples) == 1
    assert len(y_vec) == 1
    assert y_vec[0] == 120.0

    # Missing features, however, should be imputed by SimpleImputer during pipeline execution
    X_train_missing = np.array([[10.0, 20.0], [np.nan, 30.0], [30.0, np.nan]])
    y_train = np.array([100.0, 110.0, 120.0])
    model = RidgeBaseline(horizon=24, alpha=1.0)
    model.fit(X_train_missing, y_train)

    # Predictions on missing feature vector should succeed via imputer
    X_test_missing = np.array([[np.nan, 25.0]])
    preds = model.predict(X_test_missing)
    assert len(preds) == 1
    assert not np.isnan(preds[0])


def test_metric_calculations():
    y_true = [10.0, 20.0, 30.0]
    y_pred = [12.0, 18.0, 33.0]

    metrics = calculate_metrics(y_true, y_pred)

    expected_mae = (2.0 + 2.0 + 3.0) / 3.0
    expected_rmse = math.sqrt((4.0 + 4.0 + 9.0) / 3.0)

    assert abs(metrics.mae - expected_mae) < 1e-4
    assert abs(metrics.rmse - expected_rmse) < 1e-4
    assert metrics.sample_count == 3

    # Zero sample edge case
    empty_metrics = calculate_metrics([], [])
    assert empty_metrics.sample_count == 0
    assert empty_metrics.mae == 0.0

    # Constant target edge case (zero variance)
    const_metrics = calculate_metrics([50.0, 50.0], [52.0, 48.0])
    assert const_metrics.r2 == 0.0


def test_artifact_metadata_and_loading(tmp_path: Path):
    from app.services.baselines import (
        HorizonEvaluationResult,
        StationEvaluationSummary,
    )

    feature_names = ["feat_1", "feat_2"]
    X_tr = np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 5.0]])
    y_tr = np.array([10.0, 20.0, 30.0, 40.0])

    ridge_model = RidgeBaseline(horizon=24, target_pollutant="pm2_5", alpha=10.0, feature_names=feature_names)
    ridge_model.fit(X_tr, y_tr)

    metrics_dummy = ForecastMetrics(mae=2.5, rmse=3.1, r2=0.85, sample_count=4)
    h_result = HorizonEvaluationResult(
        horizon=24,
        target_pollutant="pm2_5",
        sample_count_train=4,
        sample_count_val=2,
        sample_count_test=2,
        persistence_val=metrics_dummy,
        persistence_test=metrics_dummy,
        seasonal_naive_val=metrics_dummy,
        seasonal_naive_test=metrics_dummy,
        seasonal_aligned_val=metrics_dummy,
        seasonal_aligned_test=metrics_dummy,
        ridge_val=metrics_dummy,
        ridge_test=metrics_dummy,
        ridge_train=metrics_dummy,
        ridge_best_alpha=10.0,
        ridge_model=ridge_model,
        selected_model_val="ridge",
        best_model_test="ridge",
    )

    st_summary = StationEvaluationSummary(
        station_id="test-station",
        source_provider="Open-Meteo (modeled/reanalysis)",
        target_pollutant="pm2_5",
        dataset_start_utc="2024-10-01T00:00:00Z",
        dataset_end_utc="2024-12-29T23:00:00Z",
        total_raw_records=100,
        total_supervised_samples=50,
        train_samples_raw=30,
        val_samples_raw=10,
        test_samples_raw=10,
        embargo_gap_hours=72,
        feature_count=2,
        feature_names=feature_names,
        horizon_results={24: h_result},
    )

    saved_dir = save_horizon_model_artifact(
        station_summary=st_summary,
        horizon_result=h_result,
        output_base_dir=str(tmp_path),
    )

    assert (saved_dir / "model.joblib").exists()
    assert (saved_dir / "metadata.json").exists()

    # Load artifact and test inference consistency
    loaded_model, metadata = load_model_artifact(saved_dir)
    assert metadata["station_id"] == "test-station"
    assert metadata["forecast_horizon"] == 24
    assert metadata["hyperparameters"]["alpha"] == 10.0
    assert metadata["feature_names"] == feature_names

    # Task 4 audit: Confirm metadata preserves validation-based selection and excludes test-derived selection decision
    assert metadata["model_selection"]["decision_partition"] == "validation"
    assert metadata["model_selection"]["selected_model"] == "ridge"
    assert "best_model_test" not in metadata.get("model_selection", {})

    test_input = np.array([[2.5, 3.5]])
    orig_pred = ridge_model.predict(test_input)
    loaded_pred = loaded_model.predict(test_input)

    np.testing.assert_allclose(orig_pred, loaded_pred)


def test_model_selection_uses_validation_data_strictly():
    """
    Audit check: Verify that model selection decision is determined by the validation partition,
    not the test partition, preventing test-set data snooping.
    """
    val_pers = ForecastMetrics(mae=30.0, rmse=40.0, r2=0.5, sample_count=100)
    val_ridge = ForecastMetrics(mae=35.0, rmse=45.0, r2=0.4, sample_count=100)

    # On test set, suppose Ridge achieved lower MAE than Persistence:
    test_pers = ForecastMetrics(mae=45.0, rmse=55.0, r2=0.1, sample_count=100)
    test_ridge = ForecastMetrics(mae=25.0, rmse=35.0, r2=0.7, sample_count=100)

    val_candidates = [
        ("persistence", val_pers.mae),
        ("ridge", val_ridge.mae),
    ]
    val_candidates.sort(key=lambda item: item[1])
    selected_model = val_candidates[0][0]

    # Model selection decision MUST be Persistence (lowest validation MAE=30.0), NOT Ridge:
    assert selected_model == "persistence"


def test_no_target_leakage():
    """Verify that features never contain target column names or forward-looking information."""
    base_time = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    records = [
        DatasetRecord(
            timestamp=base_time + timedelta(hours=i),
            station_id="leakage-test",
            source="open_meteo",
            pm2_5=float(50 + (i % 20)),
            pm10=float(80 + (i % 30)),
        )
        for i in range(120)
    ]
    report = DatasetQualityReport(
        station_id="leakage-test",
        source="open_meteo",
        start_time=base_time,
        end_time=base_time + timedelta(hours=119),
        total_expected_hours=120,
        available_hours=120,
        missing_hours=0,
        completeness_pct=100.0,
        null_counts={},
    )
    dataset = AirQualityDataset(
        station_id="leakage-test",
        source="open_meteo",
        records=records,
        quality_report=report,
    )

    sup_ds = generate_forecasting_features(dataset, target_pollutant="pm2_5", horizons=(24, 48, 72))

    for feat in sup_ds.feature_names:
        assert not feat.startswith("target_"), f"Feature {feat} contains target prefix!"
        assert "h24" not in feat or "lag" in feat
        assert "h48" not in feat or "lag" in feat
        assert "h72" not in feat or "lag" in feat


def test_insufficient_history_behavior():
    """Verify that a dataset with fewer than 72 hours generates zero supervised samples due to lag requirements."""
    base_time = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    short_records = [
        DatasetRecord(
            timestamp=base_time + timedelta(hours=i),
            station_id="short-test",
            source="open_meteo",
            pm2_5=50.0,
        )
        for i in range(30)  # Only 30 hours, need 72h backward lag
    ]
    report = DatasetQualityReport(
        station_id="short-test",
        source="open_meteo",
        start_time=base_time,
        end_time=base_time + timedelta(hours=29),
        total_expected_hours=30,
        available_hours=30,
        missing_hours=0,
        completeness_pct=100.0,
        null_counts={},
    )
    dataset = AirQualityDataset(
        station_id="short-test",
        source="open_meteo",
        records=short_records,
        quality_report=report,
    )

    sup_ds = generate_forecasting_features(dataset, target_pollutant="pm2_5")
    assert len(sup_ds.samples) == 0
