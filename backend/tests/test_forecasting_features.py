from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.services.dataset_builder import AirQualityDataset, DatasetQualityReport, DatasetRecord
from app.services.forecasting_features import (
    DEFAULT_HORIZONS,
    SupervisedDataset,
    SupervisedSample,
    generate_forecasting_features,
)


def _build_synthetic_dataset(num_hours: int = 120) -> AirQualityDataset:
    """Helper creating deterministic continuous series to rigorously test feature mathematics."""
    start_t = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    records = []
    for h in range(num_hours):
        t = start_t + timedelta(hours=h)
        # Value = 100 + h for easy analytical verification of lags
        records.append(
            DatasetRecord(
                timestamp=t,
                station_id="test-station",
                source="open_meteo",
                pm2_5=float(100.0 + h),
                pm10=float(200.0 + h),
                no2=float(30.0 + (h % 24)),
                so2=15.0,
                co=0.5,
                o3=40.0,
            )
        )
    report = DatasetQualityReport(
        station_id="test-station",
        source="open_meteo",
        start_time=start_t,
        end_time=start_t + timedelta(hours=num_hours - 1),
        total_expected_hours=num_hours,
        available_hours=num_hours,
        missing_hours=0,
        completeness_pct=100.0,
        null_counts={},
    )
    return AirQualityDataset("test-station", "open_meteo", records, report)


def test_autoregressive_lags_and_causal_correctness():
    """Verify autoregressive lags match historical values t_0 - k analytically."""
    ds = _build_synthetic_dataset(num_hours=120)
    sup = generate_forecasting_features(ds, target_pollutant="pm2_5", horizons=(24, 48))

    assert len(sup.samples) > 0
    # First sample should be at t_0 = start + 72 hours (since lag 72h is required)
    s0 = sup.samples[0]
    expected_t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc) + timedelta(hours=72)
    assert s0.timestamp == expected_t0

    # At t_0 = 72, pm2_5_current = 100 + 72 = 172.0
    assert s0.features["pm2_5_current"] == 172.0
    # Lag 1h = value at hour 71 = 171.0
    assert s0.features["pm2_5_lag_1h"] == 171.0
    # Lag 24h = value at hour 48 = 148.0
    assert s0.features["pm2_5_lag_24h"] == 148.0
    # Lag 72h = value at hour 0 = 100.0
    assert s0.features["pm2_5_lag_72h"] == 100.0


def test_future_targets_formulation():
    """Verify target values at t_0 + h match future observations."""
    ds = _build_synthetic_dataset(num_hours=120)
    sup = generate_forecasting_features(ds, target_pollutant="pm2_5", horizons=(24, 48))

    s0 = sup.samples[0]
    # At t_0 = hour 72:
    # Target 24h = value at hour 72 + 24 = hour 96 -> 100 + 96 = 196.0
    assert s0.targets["target_pm2_5_h24"] == 196.0
    # Target 48h = value at hour 72 + 48 = hour 120 -> out of bounds -> None
    assert s0.targets["target_pm2_5_h48"] is None


def test_zero_look_ahead_leakage_guarantee():
    """
    CRITICAL: Verify that NO future target variables appear in the feature dictionary.
    """
    ds = _build_synthetic_dataset(num_hours=120)
    sup = generate_forecasting_features(ds, target_pollutant="pm2_5", horizons=(24, 48, 72))

    for sample in sup.samples:
        for feat_name in sample.features.keys():
            assert "target" not in feat_name
            assert "future" not in feat_name


def test_rolling_statistics_strictly_backward():
    """Verify rolling statistics use past values [t_0 - w + 1, t_0] only."""
    ds = _build_synthetic_dataset(num_hours=120)
    sup = generate_forecasting_features(ds, target_pollutant="pm2_5", horizons=(24,))

    s0 = sup.samples[0]
    # At t_0 = hour 72, past 6 hours are hours 67, 68, 69, 70, 71, 72
    # Values: 167, 168, 169, 170, 171, 172. Mean = 169.5
    assert pytest.approx(s0.features["pm2_5_roll_6h_mean"], rel=1e-5) == 169.5


def test_cyclical_temporal_features_bounds():
    """Verify sine and cosine cyclical features remain strictly bounded in [-1.0, 1.0]."""
    ds = _build_synthetic_dataset(num_hours=120)
    sup = generate_forecasting_features(ds, target_pollutant="pm2_5")

    for sample in sup.samples:
        assert -1.0 <= sample.features["time_hour_sin"] <= 1.0
        assert -1.0 <= sample.features["time_hour_cos"] <= 1.0
        assert -1.0 <= sample.features["time_month_sin"] <= 1.0
        assert -1.0 <= sample.features["time_month_cos"] <= 1.0
        assert sample.features["time_is_weekend"] in (0.0, 1.0)
        assert 0.0 <= sample.features["time_day_of_week"] <= 6.0


def test_chronological_train_val_test_split_with_embargo():
    """
    Verify chronological splitting guarantees strict temporal ordering
    and enforces an embargo gap to prevent target horizon overlap.
    """
    # 600 hours synthetic series (provides sufficient span so 20% validation split exceeds 72h embargo)
    ds = _build_synthetic_dataset(num_hours=600)
    sup = generate_forecasting_features(ds, target_pollutant="pm2_5", horizons=(24, 48, 72))

    train, val, test = sup.train_val_test_split(
        train_ratio=0.60,
        val_ratio=0.20,
        embargo_gap_hours=72,
    )

    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0

    # 1. Temporal ordering: all train samples before all val samples
    max_train_time = max(s.timestamp for s in train)
    min_val_time = min(s.timestamp for s in val)
    assert min_val_time > max_train_time

    # 2. Embargo gap enforcement: gap between train and val >= 72 hours
    gap_hours = (min_val_time - max_train_time).total_seconds() / 3600.0
    assert gap_hours >= 72.0

    # 3. Temporal ordering: all val samples before all test samples
    max_val_time = max(s.timestamp for s in val)
    min_test_time = min(s.timestamp for s in test)
    assert min_test_time > max_val_time
    gap_val_test = (min_test_time - max_val_time).total_seconds() / 3600.0
    assert gap_val_test >= 72.0


def test_168_hourly_records_sample_counts():
    """
    Validation Test: Confirm whether exactly 168 hourly records produce valid supervised samples
    for a full 72-hour forecast (+24h, +48h, +72h).
    """
    ds_168 = _build_synthetic_dataset(num_hours=168)
    sup_default = generate_forecasting_features(ds_168, require_all_targets=False)

    # 1. Total samples with complete history (t_0 >= 72): 168 - 72 = 96 samples
    assert len(sup_default.samples) == 96

    # 2. Exactly 24 samples have complete future targets for the full 72h horizon:
    # Anchor t_0 from hour 72 to hour 95 (95 + 72 = 167 <= 167)
    complete_72h = sup_default.get_complete_samples(horizon=72)
    assert len(complete_72h) == 24

    # 3. Exactly 48 samples have +48h target:
    complete_48h = sup_default.get_complete_samples(horizon=48)
    assert len(complete_48h) == 48

    # 4. Exactly 72 samples have +24h target:
    complete_24h = sup_default.get_complete_samples(horizon=24)
    assert len(complete_24h) == 72

    # 5. When require_all_targets=True, exactly 24 samples are generated:
    sup_strict = generate_forecasting_features(ds_168, require_all_targets=True)
    assert len(sup_strict.samples) == 24

