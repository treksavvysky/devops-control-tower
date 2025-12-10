"""Database configuration and base setup for DevOps Control Tower."""

import os
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine
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
    # Use render_as_string with hide_password=False to preserve the actual password
    # str(url) would mask the password with *** which breaks authentication
    return _ensure_sync_driver(url).render_as_string(hide_password=False)


_engine: Optional[Engine] = None

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
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        connect_args={"connect_timeout": 10},
    )

def get_engine() -> Engine:
    """
    Create and cache the database engine.

    This is lazy-loaded to ensure environment variables are read at runtime,
    not at module import time (which would happen during Docker build).
    """
    global _engine
    if _engine is not None:
        return _engine

    database_url = get_database_url()

    if database_url.startswith("sqlite"):
        # SQLite configuration for development/testing
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL configuration for production
        _engine = create_engine(
            database_url,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    return _engine


# Backwards compatibility: expose engine as a property that calls get_engine()
# This ensures the engine is created lazily when first accessed
class _EngineProxy:
    """Proxy to lazily access the engine."""

    def __getattr__(self, name: str):
        return getattr(get_engine(), name)


engine = _EngineProxy()


def get_session_local() -> sessionmaker:
    """Get a sessionmaker bound to the current engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


async def init_database() -> None:
    """Initialize the database with all tables."""
    # Import all models to ensure they're registered with Base
    from . import models  # noqa: F401

    # Create all tables
    Base.metadata.create_all(bind=get_engine())

    print("Database initialized successfully!")


async def drop_database() -> None:
    """Drop all database tables. Use with caution!"""
    from . import models  # noqa: F401

    Base.metadata.drop_all(bind=get_engine())
    print("Database tables dropped!")


# For backwards compatibility - lazy SessionLocal
def __getattr__(name: str):
    if name == "SessionLocal":
        return get_session_local()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
