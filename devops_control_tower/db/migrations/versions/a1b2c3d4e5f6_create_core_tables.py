"""Create core tables (events, workflows, agents)

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-01-26

This migration creates the foundational tables for DevOps Control Tower:
- events: Event queue for orchestration
- workflows: Workflow definitions
- agents: AI agent registry

These tables were previously created via init_database() but are now
managed by Alembic for consistent schema management.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================
    # 1. Create events table
    # ===========================================
    # Enum types are created automatically by SQLAlchemy's create_table
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "critical", name="event_priority", create_constraint=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("tags", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="event_status", create_constraint=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by", sa.String(length=100), nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    # Events indexes
    op.create_index("ix_events_type", "events", ["type"])
    op.create_index("ix_events_source", "events", ["source"])
    op.create_index("ix_events_priority", "events", ["priority"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_type_status", "events", ["type", "status"])
    op.create_index("ix_events_created_at", "events", ["created_at"])
    op.create_index("ix_events_priority_status", "events", ["priority", "status"])

    # ===========================================
    # 2. Create workflows table
    # ===========================================
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("trigger_events", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("trigger_conditions", sa.Text, nullable=True),
        sa.Column("steps", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("idle", "running", "completed", "failed", "cancelled", name="workflow_status", create_constraint=False),
            nullable=False,
            server_default="idle",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_execution_context", sa.JSON, nullable=True),
        sa.Column("last_result", sa.JSON, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="3600"),
        sa.UniqueConstraint("name", name="uq_workflows_name"),
    )

    # Workflows indexes
    op.create_index("ix_workflows_name", "workflows", ["name"])
    op.create_index("ix_workflows_status", "workflows", ["status"])
    op.create_index("ix_workflows_is_active", "workflows", ["is_active"])
    op.create_index("ix_workflows_status_active", "workflows", ["status", "is_active"])
    op.create_index("ix_workflows_last_executed", "workflows", ["last_executed_at"])

    # ===========================================
    # 3. Create agents table
    # ===========================================
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("capabilities", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("inactive", "starting", "running", "stopping", "error", name="agent_status", create_constraint=False),
            nullable=False,
            server_default="inactive",
        ),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_status", sa.String(length=20), nullable=False, server_default="'unknown'"),
        sa.Column("health_details", sa.JSON, nullable=True),
        sa.Column("tasks_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tasks_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("average_response_time", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("auto_restart", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("max_concurrent_tasks", sa.Integer, nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("name", name="uq_agents_name"),
    )

    # Agents indexes
    op.create_index("ix_agents_name", "agents", ["name"])
    op.create_index("ix_agents_type", "agents", ["type"])
    op.create_index("ix_agents_status", "agents", ["status"])
    op.create_index("ix_agents_health_status", "agents", ["health_status"])
    op.create_index("ix_agents_is_enabled", "agents", ["is_enabled"])
    op.create_index("ix_agents_type_status", "agents", ["type", "status"])
    op.create_index("ix_agents_health_enabled", "agents", ["health_status", "is_enabled"])
    op.create_index("ix_agents_last_activity", "agents", ["last_activity_at"])


def downgrade() -> None:
    # Get the current database dialect for conditional logic
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop agents
    op.drop_table("agents")

    # Drop workflows
    op.drop_table("workflows")

    # Drop events
    op.drop_table("events")

    # Drop enums (PostgreSQL only)
    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS agent_status")
        op.execute("DROP TYPE IF EXISTS workflow_status")
        op.execute("DROP TYPE IF EXISTS event_status")
        op.execute("DROP TYPE IF EXISTS event_priority")
