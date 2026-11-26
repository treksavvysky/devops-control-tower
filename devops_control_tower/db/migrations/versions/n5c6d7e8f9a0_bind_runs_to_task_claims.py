"""Bind CWOM runs to the task claim attempt; explicit proof stage

Adds cwom_runs.task_id, cwom_runs.claim_generation and cwom_runs.proof_status
(DEVOPS-CON-11, PR #12 review C1/N2). Lifecycle code selects the runs of one
claim attempt by (task_id, claim_generation) instead of every running run on
the issue; proof_status="pending" marks an accepted result whose proof/review
has not committed yet, so it can be recovered idempotently.

Operational note: downgrading drops these bindings. Quiesce executors before
migrating or rolling back; claim tokens issued before a rollback must not be
reused afterwards (claim_generation resets with m4b5c6d7e8f9's downgrade).

Revision ID: n5c6d7e8f9a0
Revises: m4b5c6d7e8f9
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "n5c6d7e8f9a0"
down_revision = "m4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cwom_runs", sa.Column("task_id", sa.String(36), nullable=True))
    op.add_column(
        "cwom_runs", sa.Column("claim_generation", sa.Integer(), nullable=True)
    )
    op.add_column("cwom_runs", sa.Column("proof_status", sa.String(16), nullable=True))
    op.create_index(
        "ix_cwom_runs_task_claim", "cwom_runs", ["task_id", "claim_generation"]
    )
    op.create_index("ix_cwom_runs_proof_status", "cwom_runs", ["proof_status"])


def downgrade() -> None:
    op.drop_index("ix_cwom_runs_proof_status", table_name="cwom_runs")
    op.drop_index("ix_cwom_runs_task_claim", table_name="cwom_runs")
    with op.batch_alter_table("cwom_runs") as batch:
        batch.drop_column("proof_status")
        batch.drop_column("claim_generation")
        batch.drop_column("task_id")
