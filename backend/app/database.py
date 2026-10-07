from typing import Generator, Optional
from fastapi import HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base class for all Vayu AI database models."""
    pass


# Global engine and sessionmaker references
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def get_engine() -> Optional[Engine]:
    """
    Get or initialize the SQLAlchemy engine.
    Returns None if DATABASE_URL is not configured.
    """
    global _engine, _SessionLocal
    db_url = settings.normalized_database_url

    if not db_url:
        return None

    if _engine is None:
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            future=True,
        )
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_engine,
            expire_on_commit=False,
        )

    return _engine


def get_sessionmaker() -> Optional[sessionmaker[Session]]:
    """Return the sessionmaker factory bound to the active engine."""
    get_engine()
    return _SessionLocal


# Initialize on import if DATABASE_URL is already present
if settings.normalized_database_url:
    get_engine()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a managed SQLAlchemy session.
    Ensures sessions are cleanly closed after each request.
    Raises 503 if DATABASE_URL is not configured.
    """
    session_factory = get_sessionmaker()
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "DatabaseNotConfigured",
                "message": "PostgreSQL database is not configured. Set DATABASE_URL in your environment.",
            },
        )

    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> dict:
    """
    Check the current operational status of the PostgreSQL connection.
    Returns a structured status dictionary without throwing uncaught exceptions.
    """
    if not settings.normalized_database_url:
        return {
            "status": "not_configured",
            "configured": False,
            "message": "DATABASE_URL is not configured in environment.",
        }

    engine = get_engine()
    if engine is None:
        return {
            "status": "not_configured",
            "configured": False,
            "message": "Engine could not be initialized from DATABASE_URL.",
        }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "configured": True,
            "message": "PostgreSQL database connection verified.",
        }
    except Exception as exc:
        return {
            "status": "disconnected",
            "configured": True,
            "message": f"PostgreSQL connection error: {str(exc)}",
        }
