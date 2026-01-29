"""Create audit_log table

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-01-26

Adds the audit_log table for forensics and event sourcing.
Every significant state change is recorded with before/after snapshots.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Actor columns
        sa.Column(
            "actor_kind",
            sa.Enum(
                "human", "agent", "system",
                name="audit_actor_kind",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        # Action column
        sa.Column(
            "action",
            sa.Enum(
                "created", "updated", "status_changed", "deleted", "linked", "unlinked",
                name="audit_action",
                create_constraint=True,
            ),
            nullable=False,
        ),
        # Entity columns
        sa.Column("entity_kind", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        # State columns (JSON)
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        # Additional context
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
    )

    # Create indexes for common query patterns
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_entity_kind", "audit_log", ["entity_kind"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_trace_id", "audit_log", ["trace_id"])

    # Composite indexes for common query patterns
    op.create_index(
        "ix_audit_log_entity",
        "audit_log",
        ["entity_kind", "entity_id"],
    )
    op.create_index(
        "ix_audit_log_actor",
        "audit_log",
        ["actor_kind", "actor_id"],
    )
    op.create_index(
        "ix_audit_log_ts_action",
        "audit_log",
        ["ts", "action"],
    )
    op.create_index(
        "ix_audit_log_entity_ts",
        "audit_log",
        ["entity_kind", "entity_id", "ts"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_audit_log_entity_ts", table_name="audit_log")
    op.drop_index("ix_audit_log_ts_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_trace_id", table_name="audit_log")
    op.drop_index("ix_audit_log_entity_id", table_name="audit_log")
    op.drop_index("ix_audit_log_entity_kind", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")
    op.drop_index("ix_audit_log_ts", table_name="audit_log")

    # Drop table
    op.drop_table("audit_log")

    # Drop PostgreSQL enum types (no-op for SQLite)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS audit_action")
        op.execute("DROP TYPE IF EXISTS audit_actor_kind")
