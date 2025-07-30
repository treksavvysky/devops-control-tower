from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class Task(Base):
    """Unit of work to be executed."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    payload = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="pending")

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return f"<Task id={self.id} status={self.status}>"


__all__ = ["Base", "Task"]
