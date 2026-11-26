"""Add tasks.claim_generation (claim fencing token)

Revision ID: m4b5c6d7e8f9
Revises: l3a4b5c6d7e8
Create Date: 2026-11-25

Every claim increments claim_generation; every lifecycle write (finish, hold,
requeue, resolve) compares on it, so a stale holder or stale reaper can't act
on a newer claim of the same task (ABA). George: blocking correctness
requirement (DEVOPS-CON-11, review finding N1).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m4b5c6d7e8f9"
down_revision = "l3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("claim_generation", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tasks", "claim_generation")
