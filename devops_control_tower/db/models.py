from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class Job(Base):
    """A collection of tasks that represent a higher-level job."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tasks = relationship("Task", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return f"<Job id={self.id} name={self.name}>"


class Task(Base):
    """Unit of work executed as part of a job."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship("Job", back_populates="tasks")
    artifacts = relationship(
        "Artifact", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return f"<Task id={self.id} name={self.name} status={self.status}>"


class Artifact(Base):
    """Artifact produced by a task."""

    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    name = Column(String(255), nullable=False)
    uri = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="artifacts")

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return f"<Artifact id={self.id} name={self.name}>"


__all__ = ["Base", "Job", "Task", "Artifact"]
