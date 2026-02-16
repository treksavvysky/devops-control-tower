"""Add cwom_evidence_packs table for proof/verification

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2026-02-04

Adds EvidencePack CWOM object for proving that Run outputs
meet acceptance criteria. Step 4: Prove → Evidence Pack.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "i0d1e2f3a4b5"
down_revision = "h9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Verdict enum - created automatically by create_table below
    verdict_enum = sa.Enum(
        "pass", "fail", "partial", "pending",
        name="cwom_verdict",
    )

    # Criterion status enum - not used in table columns but needed by app code
    criterion_status_enum = sa.Enum(
        "satisfied", "not_satisfied", "unverified", "skipped",
        name="cwom_criterion_status",
    )
    criterion_status_enum.create(bind, checkfirst=True)

    # Create evidence_packs table
    op.create_table(
        "cwom_evidence_packs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, default="EvidencePack"),
        sa.Column("trace_id", sa.String(36), nullable=True, index=True),

        # Run reference
        sa.Column("for_run_id", sa.String(128), sa.ForeignKey("cwom_runs.id"), nullable=False, index=True),
        sa.Column("for_run_kind", sa.String(20), nullable=False, default="Run"),
        sa.Column("for_run_role", sa.String(64), nullable=True),

        # Issue reference
        sa.Column("for_issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), nullable=False, index=True),
        sa.Column("for_issue_kind", sa.String(20), nullable=False, default="Issue"),
        sa.Column("for_issue_role", sa.String(64), nullable=True),

        # Verdict
        sa.Column("verdict", verdict_enum, nullable=False, index=True),
        sa.Column("verdict_reason", sa.Text, nullable=False),

        # Evaluation details
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evaluated_by_kind", sa.Enum("human", "agent", "system", name="cwom_actor_kind", create_type=False), nullable=False),
        sa.Column("evaluated_by_id", sa.String(128), nullable=False),
        sa.Column("evaluated_by_display", sa.String(256), nullable=True),

        # Results (JSON)
        sa.Column("criteria_results", sa.JSON, nullable=False, default=list),
        sa.Column("evidence_collected", sa.JSON, nullable=False, default=list),
        sa.Column("evidence_missing", sa.JSON, nullable=False, default=list),

        # Check counts
        sa.Column("checks_passed", sa.Integer, nullable=False, default=0),
        sa.Column("checks_failed", sa.Integer, nullable=False, default=0),
        sa.Column("checks_skipped", sa.Integer, nullable=False, default=0),

        # Storage
        sa.Column("evidence_uri", sa.String(2000), nullable=True),

        # Metadata
        sa.Column("tags", sa.JSON, nullable=False, default=list),
        sa.Column("meta", sa.JSON, nullable=False, default=dict),

        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Note: Indexes on verdict, evaluated_at, created_at are created via table definition
    # Additional composite indexes can be added here if needed


def downgrade() -> None:
    op.drop_index("ix_cwom_evidence_packs_created_at", table_name="cwom_evidence_packs")
    op.drop_index("ix_cwom_evidence_packs_evaluated_at", table_name="cwom_evidence_packs")
    op.drop_index("ix_cwom_evidence_packs_verdict", table_name="cwom_evidence_packs")
    op.drop_table("cwom_evidence_packs")

    # Drop enums
    sa.Enum(name="cwom_criterion_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cwom_verdict").drop(op.get_bind(), checkfirst=True)
