import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.dataset_builder import AirQualityDataset, DatasetRecord


# Predefined feature and horizon constants
DEFAULT_HORIZONS: Tuple[int, int, int] = (24, 48, 72)
AUTOREGRESSIVE_LAGS: Tuple[int, ...] = (1, 2, 3, 6, 12, 24, 48, 72)
CO_POLLUTANT_LAGS: Tuple[int, ...] = (1, 6, 24)


@dataclass
class SupervisedSample:
    """
    A single point-in-time supervised training sample.

    Provenance & Anti-Leakage Rules:
    - timestamp represents forecast reference time t_0.
    - features are computed STRICTLY using past or current values: t <= t_0.
    - targets represent ground-truth observations at future steps: t_0 + h (where h in horizons).
    - No target values are ever permitted within the feature vector.
    """
    timestamp: datetime
    station_id: str
    features: Dict[str, float] = field(default_factory=dict)
    targets: Dict[str, Optional[float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "station_id": self.station_id,
            "features": self.features,
            "targets": self.targets,
        }


@dataclass
class SupervisedDataset:
    """Supervised learning dataset containing chronological feature samples and split utilities."""
    samples: List[SupervisedSample]
    feature_names: List[str]
    target_names: List[str]
    target_pollutant: str
    horizons: Tuple[int, ...]

    def train_val_test_split(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        embargo_gap_hours: int = 72,
    ) -> Tuple[List[SupervisedSample], List[SupervisedSample], List[SupervisedSample]]:
        """
        Chronological temporal train/validation/test split with anti-leakage embargo.

        Guarantees:
        - Strictly temporal partition (no shuffling, no future information leaking into past).
        - Embargo gap: An embargo buffer equal to the maximum forecast horizon (e.g. 72 hours)
          is enforced between train and validation, and between validation and test,
          ensuring future targets in the train set do not overlap with feature steps in the evaluation set.
        """
        if not self.samples:
            return [], [], []

        total_n = len(self.samples)
        train_end_idx = int(total_n * train_ratio)
        val_end_idx = int(total_n * (train_ratio + val_ratio))

        train_raw = self.samples[:train_end_idx]
        val_raw = self.samples[train_end_idx:val_end_idx]
        test_raw = self.samples[val_end_idx:]

        if not train_raw:
            return [], [], []

        # Apply temporal embargo gap between splits
        embargo_delta = timedelta(hours=embargo_gap_hours)

        train_cutoff_time = train_raw[-1].timestamp + embargo_delta
        val_filtered = [s for s in val_raw if s.timestamp > train_cutoff_time]

        if val_filtered:
            val_cutoff_time = val_raw[-1].timestamp + embargo_delta
            test_filtered = [s for s in test_raw if s.timestamp > val_cutoff_time]
        else:
            test_filtered = [s for s in test_raw if s.timestamp > train_cutoff_time]

        return train_raw, val_filtered, test_filtered

    def get_complete_samples(self, horizon: Optional[int] = None) -> List[SupervisedSample]:
        """
        Return subset of samples that have non-null targets.

        If horizon is provided (e.g. 72), checks target_{pollutant}_h{horizon}.
        If horizon is None, checks that ALL horizons in target_names are non-null.
        """
        if horizon is not None:
            target_key = f"target_{self.target_pollutant}_h{horizon}"
            return [s for s in self.samples if s.targets.get(target_key) is not None]

        return [
            s for s in self.samples
            if all(s.targets.get(k) is not None for k in self.target_names)
        ]



def _calc_mean(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    return sum(vals) / len(vals)


def _calc_std(vals: List[float]) -> Optional[float]:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    variance = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(variance)


def generate_forecasting_features(
    dataset: AirQualityDataset,
    target_pollutant: str = "pm2_5",
    horizons: Tuple[int, ...] = DEFAULT_HORIZONS,
    autoregressive_lags: Tuple[int, ...] = AUTOREGRESSIVE_LAGS,
    require_all_targets: bool = False,
) -> SupervisedDataset:
    """
    Generate supervised learning lag features, rolling statistics, and calendar features
    strictly adhering to causal ordering with zero future look-ahead data leakage.

    Features generated per reference time t_0:
    - Target Autoregressive Lags: target(t_0 - lag) for lag in (1, 2, 3, 6, 12, 24, 48, 72)
    - Co-pollutant Lags: pollutant(t_0 - lag) for lag in (1, 6, 24)
    - Backward-Looking Rolling Statistics:
      - 6-hour rolling mean, std
      - 12-hour rolling mean, min, max
      - 24-hour rolling mean, min, max, std
    - Cyclical Temporal Features:
      - hour_sin, hour_cos (diurnal periodic encoding)
      - day_of_week (0-6), is_weekend (0/1)
      - month_sin, month_cos (seasonal periodic encoding)

    Targets generated:
      - target_{pollutant}_h{horizon} = observation at t_0 + horizon
    """
    records = dataset.records
    if not records:
        return SupervisedDataset(
            samples=[],
            feature_names=[],
            target_names=[f"target_{target_pollutant}_h{h}" for h in horizons],
            target_pollutant=target_pollutant,
            horizons=horizons,
        )

    # Index records strictly by timestamp for O(1) causal lookups
    records_by_time: Dict[datetime, DatasetRecord] = {r.timestamp: r for r in records}
    sorted_timestamps = sorted(records_by_time.keys())

    target_attr = target_pollutant.lower().replace(".", "_")
    co_pollutants = [p for p in ["pm2_5", "pm10", "no2", "so2", "co", "o3"] if p != target_attr]

    feature_names_set: Set[str] = set()
    target_names = [f"target_{target_pollutant}_h{h}" for h in horizons]
    samples: List[SupervisedSample] = []

    max_backward_lag = max(autoregressive_lags)

    for i, t_0 in enumerate(sorted_timestamps):
        rec_0 = records_by_time[t_0]

        # 1. Target check at t_0: must have valid current measurement to anchor lag series
        curr_val = getattr(rec_0, target_attr, None)
        if curr_val is None:
            continue

        # 2. Extract future targets at t_0 + h
        sample_targets: Dict[str, Optional[float]] = {}
        missing_any_target = False

        for h in horizons:
            t_future = t_0 + timedelta(hours=h)
            target_key = f"target_{target_pollutant}_h{h}"
            future_rec = records_by_time.get(t_future)
            if future_rec is not None:
                future_val = getattr(future_rec, target_attr, None)
                sample_targets[target_key] = future_val
                if future_val is None:
                    missing_any_target = True
            else:
                sample_targets[target_key] = None
                missing_any_target = True

        if require_all_targets and missing_any_target:
            continue

        # 3. Construct Features (STRICTLY backward-looking: t <= t_0)
        sample_features: Dict[str, float] = {}

        # Current value (t_0)
        feat_name_curr = f"{target_attr}_current"
        sample_features[feat_name_curr] = float(curr_val)
        feature_names_set.add(feat_name_curr)

        # Autoregressive Lags: target(t_0 - k)
        has_sufficient_history = True
        for lag in autoregressive_lags:
            t_lag = t_0 - timedelta(hours=lag)
            lag_rec = records_by_time.get(t_lag)
            val = getattr(lag_rec, target_attr, None) if lag_rec else None
            feat_name = f"{target_attr}_lag_{lag}h"
            feature_names_set.add(feat_name)
            if val is not None:
                sample_features[feat_name] = float(val)
            else:
                # If major lag is missing, sample history is incomplete
                has_sufficient_history = False
                break

        if not has_sufficient_history:
            continue

        # Co-pollutant Lags: pollutant(t_0 - k)
        for copoll in co_pollutants:
            # Current value at t_0
            copoll_curr = getattr(rec_0, copoll, None)
            feat_name_curr_co = f"{copoll}_current"
            feature_names_set.add(feat_name_curr_co)
            if copoll_curr is not None:
                sample_features[feat_name_curr_co] = float(copoll_curr)
            else:
                sample_features[feat_name_curr_co] = float("nan")

            for lag in CO_POLLUTANT_LAGS:
                t_lag = t_0 - timedelta(hours=lag)
                lag_rec = records_by_time.get(t_lag)
                val = getattr(lag_rec, copoll, None) if lag_rec else None
                feat_name_co = f"{copoll}_lag_{lag}h"
                feature_names_set.add(feat_name_co)
                if val is not None:
                    sample_features[feat_name_co] = float(val)
                else:
                    sample_features[feat_name_co] = float("nan")

        # Backward Rolling Statistics over past windows [t_0 - w + 1, t_0]
        for w in (6, 12, 24):
            window_vals: List[float] = []
            for step in range(w):
                t_past = t_0 - timedelta(hours=step)
                p_rec = records_by_time.get(t_past)
                p_val = getattr(p_rec, target_attr, None) if p_rec else None
                if p_val is not None:
                    window_vals.append(float(p_val))

            if window_vals:
                mean_feat = f"{target_attr}_roll_{w}h_mean"
                sample_features[mean_feat] = _calc_mean(window_vals) or 0.0
                feature_names_set.add(mean_feat)

                if w >= 12:
                    min_feat = f"{target_attr}_roll_{w}h_min"
                    max_feat = f"{target_attr}_roll_{w}h_max"
                    sample_features[min_feat] = min(window_vals)
                    sample_features[max_feat] = max(window_vals)
                    feature_names_set.add(min_feat)
                    feature_names_set.add(max_feat)

                if w in (6, 24):
                    std_feat = f"{target_attr}_roll_{w}h_std"
                    sample_features[std_feat] = _calc_std(window_vals) or 0.0
                    feature_names_set.add(std_feat)

        # Calendar and Cyclical Features (derived purely from timestamp t_0)
        hour = t_0.hour
        day_of_week = t_0.weekday()
        month = t_0.month

        sample_features["time_hour_sin"] = math.sin(2.0 * math.pi * hour / 24.0)
        sample_features["time_hour_cos"] = math.cos(2.0 * math.pi * hour / 24.0)
        sample_features["time_day_of_week"] = float(day_of_week)
        sample_features["time_is_weekend"] = 1.0 if day_of_week in (5, 6) else 0.0
        sample_features["time_month_sin"] = math.sin(2.0 * math.pi * month / 12.0)
        sample_features["time_month_cos"] = math.cos(2.0 * math.pi * month / 12.0)

        feature_names_set.update([
            "time_hour_sin",
            "time_hour_cos",
            "time_day_of_week",
            "time_is_weekend",
            "time_month_sin",
            "time_month_cos",
        ])

        samples.append(
            SupervisedSample(
                timestamp=t_0,
                station_id=rec_0.station_id,
                features=sample_features,
                targets=sample_targets,
            )
        )

    return SupervisedDataset(
        samples=samples,
        feature_names=sorted(list(feature_names_set)),
        target_names=target_names,
        target_pollutant=target_pollutant,
        horizons=horizons,
    )
