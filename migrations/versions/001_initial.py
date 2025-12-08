"""Create initial tables

Revision ID: 001_initial
Revises:
Create Date: 2025-08-28

"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create events table
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("type", sa.String(100), nullable=False, index=True),
        sa.Column("source", sa.String(100), nullable=False, index=True),
        sa.Column("data", sa.JSON, nullable=False, default=dict),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "critical", name="event_priority"),
            nullable=False,
            default="medium",
            index=True,
        ),
        sa.Column("tags", sa.JSON, nullable=False, default=dict),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", name="event_status"
            ),
            nullable=False,
            default="pending",
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by", sa.String(100), nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    # Create indexes for events
    op.create_index("ix_events_type_status", "events", ["type", "status"])
    op.create_index("ix_events_created_at", "events", ["created_at"])
    op.create_index("ix_events_priority_status", "events", ["priority", "status"])

    # Create workflows table
    op.create_table(
        "workflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("trigger_events", sa.JSON, nullable=False, default=list),
        sa.Column("trigger_conditions", sa.Text, nullable=True),
        sa.Column("steps", sa.JSON, nullable=False, default=list),
        sa.Column(
            "status",
            sa.Enum(
                "idle",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="workflow_status",
            ),
            nullable=False,
            default="idle",
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_count", sa.Integer, nullable=False, default=0),
        sa.Column("last_execution_context", sa.JSON, nullable=True),
        sa.Column("last_result", sa.JSON, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True, index=True),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, default=3600),
    )

    # Create indexes for workflows
    op.create_index("ix_workflows_status_active", "workflows", ["status", "is_active"])
    op.create_index("ix_workflows_last_executed", "workflows", ["last_executed_at"])

    # Create agents table
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("type", sa.String(50), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", sa.JSON, nullable=False, default=dict),
        sa.Column("capabilities", sa.JSON, nullable=False, default=list),
        sa.Column(
            "status",
            sa.Enum(
                "inactive",
                "starting",
                "running",
                "stopping",
                "error",
                name="agent_status",
            ),
            nullable=False,
            default="inactive",
            index=True,
        ),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "health_status",
            sa.String(20),
            nullable=False,
            default="unknown",
            index=True,
        ),
        sa.Column("health_details", sa.JSON, nullable=True),
        sa.Column("tasks_completed", sa.Integer, nullable=False, default=0),
        sa.Column("tasks_failed", sa.Integer, nullable=False, default=0),
        sa.Column("average_response_time", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, default=True, index=True),
        sa.Column("auto_restart", sa.Boolean, nullable=False, default=True),
        sa.Column("max_concurrent_tasks", sa.Integer, nullable=False, default=5),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("error_count", sa.Integer, nullable=False, default=0),
    )

    # Create indexes for agents
    op.create_index("ix_agents_type_status", "agents", ["type", "status"])
    op.create_index(
        "ix_agents_health_enabled", "agents", ["health_status", "is_enabled"]
    )
    op.create_index("ix_agents_last_activity", "agents", ["last_activity_at"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("agents")
    op.drop_table("workflows")
    op.drop_table("events")

    # Drop custom enums
    op.execute("DROP TYPE IF EXISTS agent_status")
    op.execute("DROP TYPE IF EXISTS workflow_status")
    op.execute("DROP TYPE IF EXISTS event_status")
    op.execute("DROP TYPE IF EXISTS event_priority")
