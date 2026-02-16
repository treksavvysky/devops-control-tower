"""Add cwom_review_decisions table for review/merge gate

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2026-02-05

Adds ReviewDecision CWOM object for Step 5: Review -> Merge Gate.
Internal review only (no GitHub integration in v0).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "j1e2f3a4b5c6"
down_revision = "i0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'under_review' to cwom_status enum (for Postgres; SQLite ignores)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE cwom_status ADD VALUE IF NOT EXISTS 'under_review'")

    # Review decision status enum - created automatically by create_table below
    review_decision_status_enum = sa.Enum(
        "approved", "rejected", "needs_changes",
        name="cwom_review_decision_status",
    )

    # Create review_decisions table
    op.create_table(
        "cwom_review_decisions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, default="ReviewDecision"),
        sa.Column("trace_id", sa.String(36), nullable=True, index=True),

        # EvidencePack reference
        sa.Column("for_evidence_pack_id", sa.String(128), sa.ForeignKey("cwom_evidence_packs.id"), nullable=False, index=True),
        sa.Column("for_evidence_pack_kind", sa.String(20), nullable=False, default="EvidencePack"),
        sa.Column("for_evidence_pack_role", sa.String(64), nullable=True),

        # Run reference
        sa.Column("for_run_id", sa.String(128), sa.ForeignKey("cwom_runs.id"), nullable=False, index=True),
        sa.Column("for_run_kind", sa.String(20), nullable=False, default="Run"),
        sa.Column("for_run_role", sa.String(64), nullable=True),

        # Issue reference
        sa.Column("for_issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), nullable=False, index=True),
        sa.Column("for_issue_kind", sa.String(20), nullable=False, default="Issue"),
        sa.Column("for_issue_role", sa.String(64), nullable=True),

        # Reviewer (Actor denormalized)
        sa.Column("reviewer_kind", sa.Enum("human", "agent", "system", name="cwom_actor_kind", create_type=False), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reviewer_display", sa.String(256), nullable=True),

        # Decision
        sa.Column("decision", review_decision_status_enum, nullable=False, index=True),
        sa.Column("decision_reason", sa.Text, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        # Overrides (JSON)
        sa.Column("criteria_overrides", sa.JSON, nullable=False, default=list),

        # Metadata
        sa.Column("tags", sa.JSON, nullable=False, default=list),
        sa.Column("meta", sa.JSON, nullable=False, default=dict),

        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("cwom_review_decisions")
    sa.Enum(name="cwom_review_decision_status").drop(op.get_bind(), checkfirst=True)
