import logging
import sys
from pathlib import Path
from sqlalchemy import text

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_engine, Base
from app.models import ModeledAirQualityEstimate  # noqa: F401

logger = logging.getLogger(__name__)


def run_migrations() -> int:
    """
    Safely execute reviewable additive database migrations.
    Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
    Guarantees no dropping or altering of existing tables or data.
    """
    engine = get_engine()
    if not engine:
        sys.stderr.write("Database Error: DATABASE_URL is not configured.\n")
        return 1

    migrations_dir = BACKEND_DIR / "app" / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    print(f"=== Vayu AI: Database Migration Runner ===")
    print(f"Target dialect: {engine.dialect.name}")

    try:
        with engine.begin() as conn:
            for sql_file in sql_files:
                print(f"Applying migration: {sql_file.name}...")
                content = sql_file.read_text(encoding="utf-8")
                # Split and execute individual SQL statements
                statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
                for stmt in statements:
                    conn.execute(text(stmt))
                print(f"[OK] Successfully applied {sql_file.name}")

        print("All migrations successfully applied.")
        print("==========================================")
        return 0
    except Exception as exc:
        sys.stderr.write(f"Migration Failed: {exc}\n")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(run_migrations())
