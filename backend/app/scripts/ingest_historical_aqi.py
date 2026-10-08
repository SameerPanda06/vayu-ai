import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Ensure backend directory is in sys.path for direct module resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import get_sessionmaker
from app.services.ingestion import ingest_historical_open_meteo_data
from app.services.open_meteo_client import (
    OpenMeteoError,
    parse_date_string,
)
from app.stations import SUPPORTED_STATIONS, get_all_stations


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vayu AI -- Historical Air Quality Data Ingestion Runner",
    )
    parser.add_argument(
        "--source",
        "-s",
        choices=["open_meteo", "cpcb"],
        default="open_meteo",
        help=(
            "Historical data source: 'open_meteo' (recommended, provides free reanalysis/modeled "
            "air quality for arbitrary date windows), or 'cpcb' (official observations)."
        ),
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Start date in YYYY-MM-DD format (e.g. 2026-10-01). Required unless --recent-days is provided.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="End date in YYYY-MM-DD format (e.g. 2026-10-08). Required unless --recent-days is provided.",
    )
    parser.add_argument(
        "--recent-days",
        "-d",
        type=int,
        default=None,
        help="Ingest the most recent N completed days ending today (e.g. 7). Overrides --start and --end.",
    )
    parser.add_argument(
        "--stations",
        default=None,
        help="Optional comma-separated list of station IDs (e.g. 'anand-vihar,punjabi-bagh').",
    )
    parser.add_argument(
        "--exclude-future",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude modeled estimates with timestamps in the future (default: true).",
    )
    parser.add_argument(
        "--completed-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude incomplete in-progress hourly intervals (default: true).",
    )
    parser.add_argument(
        "--cutoff-utc",
        default=None,
        help="Optional UTC cutoff timestamp (ISO-8601). Estimates after this timestamp are excluded.",
    )
    return parser


def run_historical_ingestion(
    source: str = "open_meteo",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    recent_days: Optional[int] = None,
    station_ids: Optional[List[str]] = None,
    exclude_future: bool = True,
    completed_only: bool = True,
    cutoff_utc: Optional[str] = None,
) -> int:
    """CLI runner for historical air quality data ingestion."""
    # 1. Validate source
    source_norm = (source or "open_meteo").strip().lower()
    if source_norm == "cpcb":
        sys.stderr.write(
            "Historical Data Notice: The official CPCB OGD API (data.gov.in) provides real-time "
            "snapshots only and does not expose a public historical query endpoint for arbitrary past dates.\n"
            "Use '--source open_meteo' to ingest historical modeled atmospheric estimates.\n"
        )
        return 1

    # 2. Validate dates and recent-days mode
    if recent_days is not None:
        if recent_days < 1:
            sys.stderr.write("Configuration Error: --recent-days must be at least 1.\n")
            return 1
        now_utc = datetime.now(timezone.utc)
        end_d = now_utc.date()
        start_d = (now_utc - timedelta(days=recent_days)).date()
        start_date = start_d.isoformat()
        end_date = end_d.isoformat()
    elif not start_date or not end_date:
        sys.stderr.write(
            "Configuration Error: Provide either --recent-days (e.g. 7) or both --start and --end.\n"
        )
        return 1

    try:
        start_d = parse_date_string(start_date)
        end_d = parse_date_string(end_date)
        if end_d < start_d:
            sys.stderr.write(
                f"Date Error: end_date ({end_date}) cannot be earlier than start_date ({start_date}).\n"
            )
            return 1
    except ValueError as exc:
        sys.stderr.write(f"Date Error: {exc}\n")
        return 1

    # 3. Parse optional cutoff timestamp
    cutoff_dt: Optional[datetime] = None
    if cutoff_utc:
        try:
            cutoff_dt = datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
        except Exception as exc:
            sys.stderr.write(f"Timestamp Error: Invalid --cutoff-utc: {exc}\n")
            return 1

    # 4. Validate database
    if not settings.normalized_database_url:
        sys.stderr.write(
            "Configuration Error: DATABASE_URL is not configured.\n"
            "Please configure your PostgreSQL connection string in .env or environment.\n"
        )
        return 1

    session_factory = get_sessionmaker()
    if not session_factory:
        sys.stderr.write("Database Error: Failed to initialize PostgreSQL session factory.\n")
        return 1

    # 5. Resolve stations
    all_stations = get_all_stations()
    if station_ids:
        normalized_requested = [sid.strip().lower() for sid in station_ids if sid.strip()]
        target_stations = [s for s in all_stations if s.id in normalized_requested]
        if not target_stations:
            sys.stderr.write(
                f"Station Error: None of the requested stations {station_ids} match the catalog.\n"
                f"Supported stations: {list(SUPPORTED_STATIONS.keys())}\n"
            )
            return 1
    else:
        target_stations = all_stations

    db = session_factory()
    try:
        print("=== Vayu AI: Historical Air Quality Ingestion ===")
        print(f"Source: {source_norm}")
        print(f"Date window: {start_date} to {end_date} ({(end_d - start_d).days + 1} days)")
        print(f"Target stations: {[s.id for s in target_stations]}")
        print(f"Exclude future estimates: {exclude_future}")
        if cutoff_dt:
            print(f"Cutoff UTC: {cutoff_dt.isoformat()}")
        print("Fetching and persisting records idempotently...")

        result = ingest_historical_open_meteo_data(
            db=db,
            start_date=start_date,
            end_date=end_date,
            target_stations=target_stations,
            max_timestamp=cutoff_dt,
            exclude_future=exclude_future,
            completed_only=completed_only,
        )

        print("\n--- Ingestion Summary ---")
        print(f"Total API records fetched: {result.records_fetched}")
        print(f"Normalized estimates: {result.normalized_estimates}")
        print(f"Stations touched: {result.stations_touched}")
        print(f"Rows inserted: {result.estimates_inserted}")
        print(f"Duplicates skipped: {result.duplicates_skipped}")

        if result.station_breakdown:
            print("\nStation Breakdown:")
            for s_id, stats in result.station_breakdown.items():
                print(
                    f"  - {s_id}: {stats['normalized']} normalized, "
                    f"{stats['inserted']} inserted, {stats['skipped']} skipped"
                )

        if result.errors:
            print(f"\nReported errors: {'; '.join(result.errors)}")

        print("==================================================")
        return 0

    except OpenMeteoError as exc:
        sys.stderr.write(f"Open-Meteo API Error: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Ingestion Error: {exc}\n")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()
    requested_stations = args.stations.split(",") if args.stations else None
    sys.exit(
        run_historical_ingestion(
            source=args.source,
            start_date=args.start,
            end_date=args.end,
            recent_days=args.recent_days,
            station_ids=requested_stations,
            exclude_future=args.exclude_future,
            completed_only=args.completed_only,
            cutoff_utc=args.cutoff_utc,
        )
    )
