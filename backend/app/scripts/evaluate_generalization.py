"""
Out-of-time model generalization evaluation runner for Vayu AI.

Evaluates 2024-trained Ridge and baseline models against held-out 2026 data.
Strictly out-of-time, zero training/tuning on the evaluation period.

Exports:
- artifacts/models/out_of_time_evaluation_metrics.json
- artifacts/models/out_of_time_evaluation_metrics.csv
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_sessionmaker
from app.services.baselines import extract_feature_matrix
from app.services.dataset_builder import build_hourly_dataset
from app.services.forecasting_features import DEFAULT_HORIZONS, generate_forecasting_features
from app.services.model_persistence import load_model_artifact
from app.stations import get_all_stations, get_station_by_id

logger = logging.getLogger(__name__)


def evaluate_out_of_time(
    start_date: str = "2026-10-01",
    end_date: str = "2026-10-08",
    station_ids: Optional[List[str]] = None,
    export_json: Optional[str] = "artifacts/models/out_of_time_evaluation_metrics.json",
    export_csv: Optional[str] = "artifacts/models/out_of_time_evaluation_metrics.csv",
) -> Dict[str, Any]:
    """
    Run out-of-time evaluation across specified stations and export metrics.
    """
    session_factory = get_sessionmaker()
    if not session_factory:
        raise RuntimeError("Database session factory unavailable.")

    db = session_factory()
    stations = [get_station_by_id(s) for s in station_ids] if station_ids else get_all_stations()
    stations = [s for s in stations if s is not None]

    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00+00:00")
    end_dt = datetime.fromisoformat(f"{end_date}T09:00:00+00:00")

    results: Dict[str, Any] = {
        "evaluation_period": {"start_utc": start_dt.isoformat(), "end_utc": end_dt.isoformat()},
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "stations": {},
    }
    csv_rows: List[Dict[str, Any]] = []

    try:
        for st in stations:
            dataset = build_hourly_dataset(
                db=db,
                station_id=st.id,
                start_time=start_dt,
                end_time=end_dt,
                source="open_meteo",
            )
            sup_ds = generate_forecasting_features(
                dataset=dataset,
                target_pollutant="pm2_5",
                horizons=DEFAULT_HORIZONS,
                require_all_targets=False,
            )

            st_res: Dict[str, Any] = {
                "station_id": st.id,
                "station_name": st.name,
                "total_records": len(dataset.records),
                "total_samples": len(sup_ds.samples),
                "horizons": {},
            }

            for h in DEFAULT_HORIZONS:
                target_key = f"target_pm2_5_h{h}"
                eval_samples = [s for s in sup_ds.samples if s.targets.get(target_key) is not None]
                n_samples = len(eval_samples)
                if n_samples == 0:
                    continue

                y_true = np.array([s.targets[target_key] for s in eval_samples], dtype=float)
                y_pers = np.array([s.features["pm2_5_current"] for s in eval_samples], dtype=float)
                y_sn24 = np.array(
                    [s.features.get("pm2_5_lag_24h", s.features["pm2_5_current"]) for s in eval_samples],
                    dtype=float,
                )

                # Load 2024 Ridge artifact
                ridge_baseline, meta = load_model_artifact(f"artifacts/models/{st.id}/pm2_5_h{h}")
                x_mat = extract_feature_matrix(eval_samples, meta["feature_names"])
                y_ridge = np.maximum(0.0, ridge_baseline.pipeline.predict(x_mat))

                # Compute metrics
                mae_ridge = float(mean_absolute_error(y_true, y_ridge))
                rmse_ridge = float(np.sqrt(mean_squared_error(y_true, y_ridge)))
                r2_ridge = float(r2_score(y_true, y_ridge))

                mae_pers = float(mean_absolute_error(y_true, y_pers))
                rmse_pers = float(np.sqrt(mean_squared_error(y_true, y_pers)))
                r2_pers = float(r2_score(y_true, y_pers))

                mae_sn24 = float(mean_absolute_error(y_true, y_sn24))
                rmse_sn24 = float(np.sqrt(mean_squared_error(y_true, y_sn24)))
                r2_sn24 = float(r2_score(y_true, y_sn24))

                h_data = {
                    "sample_count": n_samples,
                    "validation_selected_model": meta.get("model_selection", {}).get("selected_model"),
                    "ridge": {"mae": round(mae_ridge, 3), "rmse": round(rmse_ridge, 3), "r2": round(r2_ridge, 4)},
                    "persistence": {"mae": round(mae_pers, 3), "rmse": round(rmse_pers, 3), "r2": round(r2_pers, 4)},
                    "seasonal_naive_24h": {"mae": round(mae_sn24, 3), "rmse": round(rmse_sn24, 3), "r2": round(r2_sn24, 4)},
                }
                st_res["horizons"][f"h{h}"] = h_data

                for m_name, m_stats in [("ridge", h_data["ridge"]), ("persistence", h_data["persistence"]), ("seasonal_naive_24h", h_data["seasonal_naive_24h"])]:
                    csv_rows.append({
                        "station_id": st.id,
                        "horizon": f"+{h}h",
                        "model": m_name,
                        "sample_count": n_samples,
                        "mae": m_stats["mae"],
                        "rmse": m_stats["rmse"],
                        "r2": m_stats["r2"],
                        "val_selected": meta.get("model_selection", {}).get("selected_model") == m_name,
                    })

            results["stations"][st.id] = st_res

        # Export JSON
        if export_json:
            p_json = Path(export_json)
            p_json.parent.mkdir(parents=True, exist_ok=True)
            with open(p_json, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

        # Export CSV
        if export_csv and csv_rows:
            p_csv = Path(export_csv)
            p_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(p_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
                writer.writeheader()
                writer.writerows(csv_rows)

        return results

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vayu AI Out-of-Time Model Generalization Evaluator")
    parser.add_argument("--start", default="2026-10-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-10-08", help="End date YYYY-MM-DD")
    args = parser.parse_args()

    res = evaluate_out_of_time(start_date=args.start, end_date=args.end)
    print("=== Out-of-Time Generalization Evaluation Summary ===")
    for s_id, s_data in res["stations"].items():
        print(f"\nStation: {s_id}")
        for h_k, h_v in s_data["horizons"].items():
            print(f"  {h_k} (N={h_v['sample_count']}): Ridge MAE={h_v['ridge']['mae']} | Pers MAE={h_v['persistence']['mae']} | Selected={h_v['validation_selected_model']}")
