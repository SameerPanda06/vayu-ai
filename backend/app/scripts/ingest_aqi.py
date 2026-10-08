import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure backend directory is in sys.path for direct module resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import get_sessionmaker
from app.services.data_gov_client import (
    DataGovAPIError,
    DataGovAuthError,
    DataGovRateLimitError,
)
from app.services.ingestion import orchestrate_aqi_ingestion
from app.services.open_meteo_client import OpenMeteoError


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vayu AI -- Air Quality Data Ingestion Runner",
    )
    parser.add_argument(
        "--source",
        "-s",
        choices=["cpcb", "open_meteo", "auto"],
        default=None,
        help=(
            "Ingestion source mode: "
            "'cpcb' (official CPCB observations only), "
            "'open_meteo' (Open-Meteo numerical estimates only), or "
            "'auto' (try CPCB first, fallback to Open-Meteo on genuine network failures). "
            "Defaults to AQI_INGESTION_SOURCE environment variable or 'cpcb'."
        ),
    )
    return parser


def run_ingestion(source: Optional[str] = None) -> int:
    """
    CLI runner for air quality ingestion.
    Supports CPCB-only, Open-Meteo-only, and Automatic Fallback modes.
    """
    # 1. Determine active source mode
    active_mode = (source or settings.aqi_ingestion_source or "cpcb").strip().lower()
    if active_mode not in ("cpcb", "open_meteo", "auto"):
        sys.stderr.write(
            f"Configuration Error: Invalid source mode '{active_mode}'. "
            "Supported values: 'cpcb', 'open_meteo', 'auto'.\n"
        )
        return 1

    # 2. Validate database configuration
    if not settings.normalized_database_url:
        sys.stderr.write(
            "Configuration Error: DATABASE_URL is not configured.\n"
            "Please configure your PostgreSQL connection string in .env or environment.\n"
        )
        return 1

    # 3. Validate CPCB credentials when CPCB is needed
    # Note: 'auto' mode requires valid credentials to attempt CPCB first;
    # missing credentials must NOT silently trigger a fallback.
    if active_mode in ("cpcb", "auto"):
        if not settings.data_gov_in_api_key:
            sys.stderr.write(
                "Configuration Error: DATA_GOV_IN_API_KEY is not configured.\n"
                "Please obtain an API key from https://data.gov.in and set DATA_GOV_IN_API_KEY in .env.\n"
            )
            return 1

    # 4. Initialize database session
    session_factory = get_sessionmaker()
    if not session_factory:
        sys.stderr.write("Database Error: Failed to initialize PostgreSQL session factory.\n")
        return 1

    db = session_factory()
    try:
        result = orchestrate_aqi_ingestion(db, mode=active_mode)

        print("=== Vayu AI: Air Quality Data Ingestion ===")
        print(f"Selected source mode: {result.selected_mode}")
        print(f"Actual provider used: {result.actual_provider}")
        print(f"API records fetched: {result.records_fetched}")
        print(f"Normalized observations or estimates: {result.normalized_count}")
        print(f"Stations touched: {result.stations_touched}")
        print(f"Inserted rows: {result.inserted_rows}")
        print(f"Duplicates skipped: {result.duplicates_skipped}")
        if result.fallback_used:
            print(f"Fallback notice: CPCB primary unavailable; fell back to Open-Meteo.")
        if result.errors:
            print(f"Reported errors: {'; '.join(result.errors)}")
        print("==========================================")
        return 0

    except DataGovAuthError as exc:
        sys.stderr.write(f"Authentication Error: {exc}\n")
        return 1
    except DataGovRateLimitError as exc:
        sys.stderr.write(f"Rate Limit Error: {exc}\n")
        return 1
    except DataGovAPIError as exc:
        sys.stderr.write(f"CPCB API Error: {exc}\n")
        return 1
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
    sys.exit(run_ingestion(source=args.source))
