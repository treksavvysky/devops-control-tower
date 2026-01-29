"""add cwom_issue_id to tasks table

Revision ID: d4a9b8c2e5f6
Revises: c3e8f9a21b4d
Create Date: 2025-01-26

Adds CWOM integration column to tasks table for Phase 4:
- cwom_issue_id: Links task to CWOM Issue for bidirectional mapping
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4a9b8c2e5f6"
down_revision = "c3e8f9a21b4d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add cwom_issue_id column to tasks table
    op.add_column(
        "tasks",
        sa.Column("cwom_issue_id", sa.String(length=128), nullable=True),
    )

    # Create index for querying tasks by CWOM issue
    op.create_index(
        "ix_tasks_cwom_issue_id",
        "tasks",
        ["cwom_issue_id"],
    )

    # Note: We intentionally do NOT add a foreign key constraint here because:
    # 1. The cwom_issues table uses ULID strings for IDs
    # 2. This allows for eventual consistency in distributed scenarios
    # 3. The relationship is validated at the application layer


def downgrade() -> None:
    op.drop_index("ix_tasks_cwom_issue_id", table_name="tasks")
    op.drop_column("tasks", "cwom_issue_id")
