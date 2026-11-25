"""Add 'held' task status and hold metadata (confirmed-termination requeue)

Revision ID: l3a4b5c6d7e8
Revises: k2f3a4b5c6d7
Create Date: 2026-11-25

An expired claim lease no longer requeues the task unless the previous holder's
termination is confirmed; otherwise the task is 'held' for operator resolution
(DEVOPS-CON-11; George's decision, 2026-11-25).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "l3a4b5c6d7e8"
down_revision = "k2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
        # older Postgres versions; use an autocommit block.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'held'")
    op.add_column(
        "tasks", sa.Column("held_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("tasks", sa.Column("held_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    # Held tasks become failed; the enum value stays on Postgres (Postgres
    # can't drop an enum value without recreating the type).
    op.execute("UPDATE tasks SET status = 'failed' WHERE status = 'held'")
    op.drop_column("tasks", "held_reason")
    op.drop_column("tasks", "held_at")
