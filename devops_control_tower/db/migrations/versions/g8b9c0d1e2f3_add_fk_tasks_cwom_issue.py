"""Add FK constraint: tasks.cwom_issue_id -> cwom_issues.id

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-02-04

Adds foreign key constraint for data integrity between tasks and CWOM issues.
This ensures tasks can only reference existing CWOM issues.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "g8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER for constraints, so use batch mode
    # This creates a new table, copies data, drops old, renames new
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_tasks_cwom_issue_id",
            "cwom_issues",
            ["cwom_issue_id"],
            ["id"],
            ondelete="SET NULL",  # If issue deleted, set task's cwom_issue_id to NULL
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_cwom_issue_id", type_="foreignkey")
