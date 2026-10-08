"""
Command-line interface to train and evaluate baseline forecasting models in Vayu AI.

Usage:
  python -m backend.app.scripts.train_baselines --station anand-vihar --pollutant pm2_5
  python -m backend.app.scripts.train_baselines --station all --pollutant pm2_5
  python -m backend.app.scripts.train_baselines --station all --export-csv metrics.csv
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import List, Optional

# Ensure backend directory is in python search path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import get_sessionmaker
from app.services.baselines import StationEvaluationSummary, evaluate_station_baselines
from app.services.model_persistence import list_saved_artifacts, save_station_artifacts
from app.stations import SUPPORTED_STATIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_baselines")

ALL_STATION_IDS = list(SUPPORTED_STATIONS.keys())


def format_table_row(cols: List[str], widths: List[int]) -> str:
    padded = [cols[i].ljust(widths[i]) if i < 3 else cols[i].rjust(widths[i]) for i in range(len(cols))]
    return " | ".join(padded)


def print_comparison_tables(summaries: List[StationEvaluationSummary]) -> None:
    headers = ["Station", "Horizon", "Model", "Test N", "MAE (ug/m3)", "RMSE (ug/m3)", "R2", "Val Pick?"]
    widths = [15, 8, 26, 7, 13, 14, 8, 10]
    separator = "-+-".join(["-" * w for w in widths])

    print("\n" + "=" * 110)
    print("VAYU AI -- BASELINE FORECASTING ENGINE EVALUATION REPORT")
    print("Provider: Open-Meteo Modeled / Reanalysis Concentrations")
    print("Notice: Results are evaluated against Open-Meteo modeled data, NOT CPCB ground truth.")
    print("Model Selection: 'Val Pick' marks the model selected strictly on Validation partition MAE.")
    print("=" * 110)

    for summary in summaries:
        print(f"\nStation: {summary.station_id.upper()} (Records: {summary.total_raw_records}, Usable Supervised: {summary.total_supervised_samples})")
        print(f"Date Range (UTC): {summary.dataset_start_utc} to {summary.dataset_end_utc}")
        print(f"Splits: Train={summary.train_samples_raw}, Val={summary.val_samples_raw}, Test={summary.test_samples_raw} (72h embargo applied)")
        print("-" * 110)
        print(format_table_row(headers, widths))
        print(separator)

        for h, res in sorted(summary.horizon_results.items()):
            n_te = str(res.sample_count_test)
            h_label = f"+{h}h"

            # 1. Persistence
            is_pick_pers = "SELECTED" if res.selected_model_val == "persistence" else ""
            print(format_table_row([
                summary.station_id,
                h_label,
                "Persistence",
                n_te,
                f"{res.persistence_test.mae:.2f}",
                f"{res.persistence_test.rmse:.2f}",
                f"{res.persistence_test.r2:.3f}",
                is_pick_pers,
            ], widths))

            # 2. Seasonal Naive (t-24h)
            is_pick_seas = "SELECTED" if res.selected_model_val == "seasonal_naive_24h" else ""
            print(format_table_row([
                summary.station_id,
                h_label,
                "Seasonal Naive (t-24h)",
                n_te,
                f"{res.seasonal_naive_test.mae:.2f}",
                f"{res.seasonal_naive_test.rmse:.2f}",
                f"{res.seasonal_naive_test.r2:.3f}",
                is_pick_seas,
            ], widths))

            # 3. Horizon-Aligned Daily Seasonal
            is_pick_aligned = "SELECTED" if res.selected_model_val == "seasonal_aligned" else ""
            print(format_table_row([
                summary.station_id,
                h_label,
                "Seasonal (Horizon-Aligned)",
                n_te,
                f"{res.seasonal_aligned_test.mae:.2f}",
                f"{res.seasonal_aligned_test.rmse:.2f}",
                f"{res.seasonal_aligned_test.r2:.3f}",
                is_pick_aligned,
            ], widths))

            # 4. Ridge
            is_pick_ridge = "SELECTED" if res.selected_model_val == "ridge" else ""
            ridge_name = f"Ridge (a={res.ridge_best_alpha})"
            print(format_table_row([
                summary.station_id,
                h_label,
                ridge_name,
                n_te,
                f"{res.ridge_test.mae:.2f}",
                f"{res.ridge_test.rmse:.2f}",
                f"{res.ridge_test.r2:.3f}",
                is_pick_ridge,
            ], widths))

            print("-" * 110)

    print("\n" + "=" * 110)


def export_metrics_to_csv(summaries: List[StationEvaluationSummary], csv_path: str) -> None:
    fieldnames = [
        "station_id",
        "horizon_hours",
        "target_pollutant",
        "model_name",
        "hyperparameter_alpha",
        "train_samples",
        "val_samples",
        "test_samples",
        "val_mae",
        "val_rmse",
        "val_r2",
        "test_mae",
        "test_rmse",
        "test_r2",
        "selected_on_validation",
        "best_on_test_informational",
        "data_provider",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for s in summaries:
            for h, res in s.horizon_results.items():
                models_info = [
                    ("persistence", "N/A", res.persistence_val, res.persistence_test, res.selected_model_val == "persistence", res.best_model_test == "persistence"),
                    ("seasonal_naive_24h", "N/A", res.seasonal_naive_val, res.seasonal_naive_test, res.selected_model_val == "seasonal_naive_24h", res.best_model_test == "seasonal_naive_24h"),
                    ("seasonal_aligned", "N/A", res.seasonal_aligned_val, res.seasonal_aligned_test, res.selected_model_val == "seasonal_aligned", res.best_model_test == "seasonal_aligned"),
                    ("ridge", str(res.ridge_best_alpha), res.ridge_val, res.ridge_test, res.selected_model_val == "ridge", res.best_model_test == "ridge"),
                ]
                for m_name, alpha_val, m_val, m_te, is_sel_val, is_best_te in models_info:
                    writer.writerow({
                        "station_id": s.station_id,
                        "horizon_hours": h,
                        "target_pollutant": s.target_pollutant,
                        "model_name": m_name,
                        "hyperparameter_alpha": alpha_val,
                        "train_samples": res.sample_count_train,
                        "val_samples": res.sample_count_val,
                        "test_samples": res.sample_count_test,
                        "val_mae": m_val.mae,
                        "val_rmse": m_val.rmse,
                        "val_r2": m_val.r2,
                        "test_mae": m_te.mae,
                        "test_rmse": m_te.rmse,
                        "test_r2": m_te.r2,
                        "selected_on_validation": is_sel_val,
                        "best_on_test_informational": is_best_te,
                        "data_provider": s.source_provider,
                    })

    logger.info("Exported evaluation metrics to CSV: %s", csv_path)

    logger.info("Exported evaluation metrics to CSV: %s", csv_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate Vayu AI baseline forecasting models."
    )
    parser.add_argument(
        "--station",
        type=str,
        default="all",
        help="Station ID to train (e.g. 'anand-vihar') or 'all' for all 6 stations.",
    )
    parser.add_argument(
        "--pollutant",
        type=str,
        default="pm2_5",
        help="Target pollutant to forecast (default: pm2_5).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2024-10-01",
        help="Start date YYYY-MM-DD (default: 2024-10-01).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2024-12-29",
        help="End date YYYY-MM-DD (default: 2024-12-29).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/models",
        help="Directory to save model artifacts and metadata (default: artifacts/models).",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default=None,
        help="Optional path to export comparative evaluation metrics to CSV.",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Optional path to export complete evaluation summaries to JSON.",
    )

    args = parser.parse_args()

    # Parse date range in UTC
    try:
        start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, tzinfo=timezone.utc
        )
        end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").replace(
            hour=23, minute=0, second=0, tzinfo=timezone.utc
        )
    except ValueError as e:
        logger.error("Invalid date format: %s. Use YYYY-MM-DD.", e)
        sys.exit(1)

    # Determine target stations
    if args.station.strip().lower() == "all":
        stations_to_run = ALL_STATION_IDS
    else:
        st_id = args.station.strip().lower()
        if st_id not in ALL_STATION_IDS:
            logger.error("Unknown station ID '%s'. Available: %s", st_id, ALL_STATION_IDS)
            sys.exit(1)
        stations_to_run = [st_id]

    logger.info("Initializing baseline training and evaluation...")
    logger.info("Stations: %s", stations_to_run)
    logger.info("Pollutant: %s", args.pollutant)
    logger.info("Window: %s to %s", start_dt.isoformat(), end_dt.isoformat())

    summaries: List[StationEvaluationSummary] = []

    session_factory = get_sessionmaker()
    if session_factory is None:
        logger.error("Could not initialize database session factory. Is DATABASE_URL configured?")
        sys.exit(1)

    db = session_factory()
    try:
        for st_id in stations_to_run:
            logger.info("Evaluating station '%s'...", st_id)
            summary = evaluate_station_baselines(
                db=db,
                station_id=st_id,
                start_time=start_dt,
                end_time=end_dt,
                target_pollutant=args.pollutant,
            )
            summaries.append(summary)

            # Save model artifacts locally
            saved_paths = save_station_artifacts(
                station_summary=summary,
                output_base_dir=args.output_dir,
            )
            logger.info("Saved %d model artifacts for station '%s'.", len(saved_paths), st_id)

    finally:
        db.close()

    # Print comparison tables
    print_comparison_tables(summaries)

    # Export if requested
    if args.export_csv:
        export_metrics_to_csv(summaries, args.export_csv)

    if args.export_json:
        json_data = [s.to_dict() for s in summaries]
        with open(args.export_json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        logger.info("Exported JSON summary to: %s", args.export_json)

    logger.info("Baseline training and evaluation complete.")


if __name__ == "__main__":
    main()
