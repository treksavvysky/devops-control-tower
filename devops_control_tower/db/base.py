"""Database configuration and base setup for DevOps Control Tower."""

import os
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Default to a local SQLite database when DATABASE_URL is not provided.
DEFAULT_DATABASE_URL = "sqlite:///./devops_control_tower.db"


def _ensure_sync_driver(url: URL) -> URL:
    """Force a synchronous driver for Alembic and the ORM engine."""

    if url.drivername.startswith("postgresql+"):
        # Normalize any async driver variants to psycopg (sync)
        if any(token in url.drivername for token in ("async", "aiopg")):
            url = url.set(drivername="postgresql+psycopg")
    elif url.drivername.startswith("sqlite+"):
        # Align async SQLite drivers to the synchronous default
        if "aiosqlite" in url.drivername:
            url = url.set(drivername="sqlite")

    return url


def get_database_url(raw_url: Optional[str] = None) -> str:
    """Return a database URL with a guaranteed synchronous driver."""

    url = make_url(raw_url or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL)
    return str(_ensure_sync_driver(url))


# Get database URL from environment with a safe local fallback
DATABASE_URL = get_database_url()

# Create engine with proper configuration
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration for development/testing
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL configuration for production
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Session configuration
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_database() -> None:
    """Initialize the database with all tables."""
    # Import all models to ensure they're registered with Base
    from . import models  # noqa: F401

    # Create all tables
    Base.metadata.create_all(bind=engine)

    print("Database initialized successfully!")


async def drop_database() -> None:
    """Drop all database tables. Use with caution!"""
    from . import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped!")
