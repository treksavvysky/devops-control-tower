"""
Database configuration and base setup for DevOps Control Tower.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/devops_control_tower"
)

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

# Base class for all models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_database():
    """Initialize the database with all tables."""
    # Import all models to ensure they're registered with Base
    from . import models  # noqa: F401
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("Database initialized successfully!")


async def drop_database():
    """Drop all database tables. Use with caution!"""
    from . import models  # noqa: F401
    
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped!")
