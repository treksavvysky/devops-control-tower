"""Sprint-0: Add trace_id support and jobs/artifacts tables

Revision ID: e5f6a7b8c9d0
Revises: d4a9b8c2e5f6
Create Date: 2025-01-26

Sprint-0 vertical slice: trace_id propagation across all layers.
- Adds trace_id column to tasks table (indexed)
- Creates jobs table for execution tracking
- Creates artifacts table for output references (separate from CWOM artifacts)
- Adds trace_id to CWOM tables for unified traceability
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4a9b8c2e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================
    # 1. Add trace_id to tasks table
    # ===========================================
    op.add_column(
        "tasks",
        sa.Column("trace_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_tasks_trace_id", "tasks", ["trace_id"])

    # ===========================================
    # 2. Create jobs table
    # ===========================================
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False, index=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "claimed", "running", "completed", "failed",
                name="job_status",
                create_constraint=True,
            ),
            nullable=False,
            default="pending",
            server_default="pending",
        ),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_worker_id", "jobs", ["worker_id"])
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"])

    # ===========================================
    # 3. Create artifacts table (Sprint-0 style)
    # ===========================================
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("job_id", sa.String(length=36), nullable=True, index=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False, index=True),
        sa.Column(
            "kind",
            sa.Enum(
                "log", "diff", "report", "file", "metric", "error",
                name="artifact_kind",
                create_constraint=True,
            ),
            nullable=False,
            default="log",
        ),
        sa.Column("uri", sa.String(length=1024), nullable=True),
        sa.Column("ref", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("meta", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"])
    op.create_index("ix_artifacts_created_at", "artifacts", ["created_at"])

    # ===========================================
    # 4. Add trace_id to CWOM tables (non-breaking)
    # ===========================================
    cwom_tables = [
        "cwom_repos",
        "cwom_issues",
        "cwom_context_packets",
        "cwom_constraint_snapshots",
        "cwom_doctrine_refs",
        "cwom_runs",
        "cwom_artifacts",
    ]

    for table in cwom_tables:
        op.add_column(
            table,
            sa.Column("trace_id", sa.String(length=36), nullable=True),
        )
        op.create_index(f"ix_{table}_trace_id", table, ["trace_id"])


def downgrade() -> None:
    # Remove trace_id from CWOM tables
    cwom_tables = [
        "cwom_repos",
        "cwom_issues",
        "cwom_context_packets",
        "cwom_constraint_snapshots",
        "cwom_doctrine_refs",
        "cwom_runs",
        "cwom_artifacts",
    ]

    for table in cwom_tables:
        op.drop_index(f"ix_{table}_trace_id", table_name=table)
        op.drop_column(table, "trace_id")

    # Drop artifacts table
    op.drop_index("ix_artifacts_created_at", table_name="artifacts")
    op.drop_index("ix_artifacts_kind", table_name="artifacts")
    op.drop_index("ix_artifacts_trace_id", table_name="artifacts")
    op.drop_index("ix_artifacts_job_id", table_name="artifacts")
    op.drop_index("ix_artifacts_task_id", table_name="artifacts")
    op.drop_table("artifacts")

    # Drop jobs table
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.drop_index("ix_jobs_worker_id", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_trace_id", table_name="jobs")
    op.drop_index("ix_jobs_task_id", table_name="jobs")
    op.drop_table("jobs")

    # Drop PostgreSQL enum types (no-op for SQLite)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS artifact_kind")
        op.execute("DROP TYPE IF EXISTS job_status")

    # Remove trace_id from tasks
    op.drop_index("ix_tasks_trace_id", table_name="tasks")
    op.drop_column("tasks", "trace_id")
