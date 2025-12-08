"""create task table (JCT V1 Task Spec)

Revision ID: b2f6a732d137
Revises:
Create Date: 2025-07-30 15:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "b2f6a732d137"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    op.execute(
        "CREATE TYPE requester_kind AS ENUM ('human', 'agent', 'system')"
    )
    op.execute(
        "CREATE TYPE operation_type AS ENUM ('code_change', 'docs', 'analysis', 'ops')"
    )
    op.execute(
        "CREATE TYPE task_status AS ENUM ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')"
    )

    # Create tasks table
    op.create_table(
        "tasks",
        # Primary fields
        sa.Column("id", UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column("version", sa.String(length=10), nullable=False, server_default="1.0"),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        # Audit information (requested_by)
        sa.Column(
            "requested_by_kind",
            sa.Enum("human", "agent", "system", name="requester_kind"),
            nullable=False,
        ),
        sa.Column("requested_by_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by_label", sa.String(length=256), nullable=True),
        # Task definition
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("code_change", "docs", "analysis", "ops", name="operation_type"),
            nullable=False,
        ),
        # Target information
        sa.Column("target_repo", sa.String(length=256), nullable=False),
        sa.Column("target_ref", sa.String(length=256), nullable=False, server_default="main"),
        sa.Column("target_path", sa.String(length=512), nullable=False, server_default=""),
        # Constraints
        sa.Column("time_budget_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("allow_network", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allow_secrets", sa.Boolean(), nullable=False, server_default="false"),
        # Task data
        sa.Column("inputs", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        # Status tracking
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="task_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Execution details
        sa.Column("assigned_to", sa.String(length=100), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("trace_path", sa.String(length=512), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_tasks_idempotency_key"),
    )

    # Create indexes
    op.create_index("ix_tasks_version", "tasks", ["version"])
    op.create_index("ix_tasks_idempotency_key", "tasks", ["idempotency_key"])
    op.create_index("ix_tasks_requested_by_kind", "tasks", ["requested_by_kind"])
    op.create_index("ix_tasks_requested_by_id", "tasks", ["requested_by_id"])
    op.create_index("ix_tasks_operation", "tasks", ["operation"])
    op.create_index("ix_tasks_target_repo", "tasks", ["target_repo"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_status_operation", "tasks", ["status", "operation"])
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"])
    op.create_index(
        "ix_tasks_requester", "tasks", ["requested_by_kind", "requested_by_id"]
    )


def downgrade() -> None:
    op.drop_table("tasks")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS operation_type")
    op.execute("DROP TYPE IF EXISTS requester_kind")
