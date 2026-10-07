import sys
from pathlib import Path

# Ensure backend directory is in sys.path for direct module resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import get_sessionmaker
from app.services.data_gov_client import DataGovAPIError, DataGovAuthError, DataGovRateLimitError
from app.services.ingestion import ingest_air_quality_data


def run_ingestion() -> int:
    """CLI runner for manual data.gov.in CPCB AQI ingestion."""
    # 1. Validate environment configuration
    if not settings.normalized_database_url:
        sys.stderr.write(
            "Configuration Error: DATABASE_URL is not configured.\n"
            "Please configure your PostgreSQL connection string in .env or environment.\n"
        )
        return 1

    if not settings.data_gov_in_api_key:
        sys.stderr.write(
            "Configuration Error: DATA_GOV_IN_API_KEY is not configured.\n"
            "Please obtain an API key from https://data.gov.in and set DATA_GOV_IN_API_KEY in .env.\n"
        )
        return 1

    # 2. Initialize database session
    session_factory = get_sessionmaker()
    if not session_factory:
        sys.stderr.write("Database Error: Failed to initialize PostgreSQL session factory.\n")
        return 1

    db = session_factory()
    try:
        result = ingest_air_quality_data(db)
        print("=== Vayu AI: CPCB AQI Data Ingestion ===")
        print(f"Fetched records: {result.fetched_records}")
        print(f"Normalized observations: {result.normalized_observations}")
        print(f"Stations inserted/updated: {result.stations_upserted}")
        print(f"Readings inserted: {result.readings_inserted}")
        print(f"Duplicates skipped: {result.duplicates_skipped}")
        print("========================================")
        return 0

    except DataGovAuthError as exc:
        sys.stderr.write(f"Authentication Error: {exc}\n")
        return 1
    except DataGovRateLimitError as exc:
        sys.stderr.write(f"Rate Limit Error: {exc}\n")
        return 1
    except DataGovAPIError as exc:
        sys.stderr.write(f"API Error: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Ingestion Error: {exc}\n")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(run_ingestion())
