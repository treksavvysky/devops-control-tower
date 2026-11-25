"""Add lease_expires_at to tasks for claim leases

Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6
Create Date: 2026-11-25

A claimed task holds a lease until lease_expires_at (time budget plus grace).
Expired claims are requeued so a lost executor cannot leave a task running
forever (DEVOPS-CON-3, gap G7).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "k2f3a4b5c6d7"
down_revision = "j1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_tasks_status_lease_expires_at",
        "tasks",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_status_lease_expires_at", table_name="tasks")
    op.drop_column("tasks", "lease_expires_at")
