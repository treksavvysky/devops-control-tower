"""
Trace storage abstraction for JCT Worker.

v0: file:// support (local filesystem)
v2: s3:// support (add S3 handler without changing worker code)

Design principle: treat storage as a URI, not a boolean.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse


class TraceStore(ABC):
    """Abstract base class for trace storage."""

    @abstractmethod
    def write(self, path: str, content: bytes) -> None:
        """Write raw bytes to a path within the trace folder."""
        pass

    @abstractmethod
    def write_text(self, path: str, content: str) -> None:
        """Write text content to a path within the trace folder."""
        pass

    @abstractmethod
    def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON data to a path within the trace folder."""
        pass

    @abstractmethod
    def append_line(self, path: str, line: str) -> None:
        """Append a line to a file (for logs)."""
        pass

    @abstractmethod
    def append_event(self, event: Dict[str, Any]) -> None:
        """Append a structured event to events.jsonl."""
        pass

    @abstractmethod
    def ensure_dir(self, path: str) -> None:
        """Ensure a directory exists within the trace folder."""
        pass

    @abstractmethod
    def get_uri(self) -> str:
        """Get the full URI of this trace store."""
        pass


class FileTraceStore(TraceStore):
    """Local filesystem trace store (file:// URIs).

    Structure:
        /var/lib/jct/runs/{run_id}/
        ├── trace.log           # Human-readable execution log
        ├── events.jsonl        # Structured events (machine-parseable)
        ├── manifest.json       # Run metadata, timestamps, final status
        └── artifacts/          # Output files
    """

    def __init__(self, base_path: Path):
        """Initialize with base path for this run's trace folder.

        Args:
            base_path: Absolute path to the run's trace folder
        """
        self.base_path = base_path
        self._ensure_base_structure()

    def _ensure_base_structure(self) -> None:
        """Create the base directory structure."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "artifacts").mkdir(exist_ok=True)

    def write(self, path: str, content: bytes) -> None:
        """Write raw bytes to a path within the trace folder."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

    def write_text(self, path: str, content: str) -> None:
        """Write text content to a path within the trace folder."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON data to a path within the trace folder."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def append_line(self, path: str, line: str) -> None:
        """Append a line to a file (for logs)."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def append_event(self, event: Dict[str, Any]) -> None:
        """Append a structured event to events.jsonl."""
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.append_line("events.jsonl", json.dumps(event, default=str))

    def ensure_dir(self, path: str) -> None:
        """Ensure a directory exists within the trace folder."""
        (self.base_path / path).mkdir(parents=True, exist_ok=True)

    def get_uri(self) -> str:
        """Get the full URI of this trace store."""
        return f"file://{self.base_path}"


def create_trace_store(uri: str, run_id: str) -> TraceStore:
    """Factory function to create appropriate TraceStore from URI.

    Args:
        uri: Base URI (e.g., "file:///var/lib/jct/runs" or "s3://bucket/prefix")
        run_id: Run ID to create trace folder for

    Returns:
        TraceStore instance for the given URI scheme

    Raises:
        ValueError: If URI scheme is not supported
    """
    parsed = urlparse(uri)

    if parsed.scheme == "file":
        # file:///var/lib/jct/runs -> /var/lib/jct/runs/{run_id}
        base_path = Path(parsed.path) / run_id
        return FileTraceStore(base_path)

    elif parsed.scheme == "s3":
        # s3://bucket/prefix -> s3://bucket/prefix/{run_id}
        # TODO: Implement S3TraceStore in v2
        raise NotImplementedError(
            f"S3 storage not yet implemented. URI: {uri}"
        )

    else:
        raise ValueError(
            f"Unsupported storage scheme: {parsed.scheme}. "
            f"Supported: file://, s3:// (v2)"
        )


def get_trace_uri(base_uri: str, run_id: str) -> str:
    """Construct full trace URI for a run.

    Args:
        base_uri: Base URI from config (e.g., "file:///var/lib/jct/runs")
        run_id: Run ID

    Returns:
        Full URI for the run's trace folder
    """
    parsed = urlparse(base_uri)

    if parsed.scheme == "file":
        return f"file://{parsed.path}/{run_id}/"
    elif parsed.scheme == "s3":
        # Normalize path (remove trailing slash, add run_id)
        path = parsed.path.rstrip("/")
        return f"s3://{parsed.netloc}{path}/{run_id}/"
    else:
        raise ValueError(f"Unsupported storage scheme: {parsed.scheme}")
