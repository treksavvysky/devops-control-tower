"""Add artifact_root_uri to cwom_runs for trace storage

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-02-04

Adds URI field for trace storage location (file:// or s3://).
This enables storage abstraction - v0 uses local filesystem,
v2 can swap to S3 without code changes.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "h9c0d1e2f3a4"
down_revision = "g8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add artifact_root_uri column to cwom_runs
    # Example values:
    #   file:///var/lib/jct/runs/{job_id}/
    #   s3://bucket/prefix/{job_id}/
    op.add_column(
        "cwom_runs",
        sa.Column("artifact_root_uri", sa.String(2000), nullable=True),
    )
    # Index for querying runs by storage location
    op.create_index(
        "ix_cwom_runs_artifact_root_uri",
        "cwom_runs",
        ["artifact_root_uri"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cwom_runs_artifact_root_uri", table_name="cwom_runs")
    op.drop_column("cwom_runs", "artifact_root_uri")
