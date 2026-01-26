"""create CWOM v0.1 tables

Revision ID: c3e8f9a21b4d
Revises: b2f6a732d137
Create Date: 2025-01-25

Creates tables for CWOM (Canonical Work Object Model) v0.1:
- cwom_repos
- cwom_issues
- cwom_context_packets
- cwom_constraint_snapshots
- cwom_doctrine_refs
- cwom_runs
- cwom_artifacts
- Join tables for many-to-many relationships
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3e8f9a21b4d"
down_revision = "b2f6a732d137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # Create CWOM Enums
    # ==========================================================================
    op.execute(
        """CREATE TYPE cwom_object_kind AS ENUM (
            'Repo', 'Issue', 'ContextPacket', 'Run', 'Artifact',
            'ConstraintSnapshot', 'DoctrineRef'
        )"""
    )
    op.execute(
        """CREATE TYPE cwom_status AS ENUM (
            'planned', 'ready', 'running', 'blocked', 'done', 'failed', 'canceled'
        )"""
    )
    op.execute(
        """CREATE TYPE cwom_issue_type AS ENUM (
            'feature', 'bug', 'chore', 'research', 'ops', 'doc', 'incident'
        )"""
    )
    op.execute(
        """CREATE TYPE cwom_priority AS ENUM ('P0', 'P1', 'P2', 'P3', 'P4')"""
    )
    op.execute(
        """CREATE TYPE cwom_run_mode AS ENUM ('human', 'agent', 'hybrid', 'system')"""
    )
    op.execute(
        """CREATE TYPE cwom_artifact_type AS ENUM (
            'code_patch', 'commit', 'pr', 'build', 'container_image',
            'doc', 'report', 'dataset', 'log', 'trace', 'binary', 'link'
        )"""
    )
    op.execute(
        """CREATE TYPE cwom_verification_status AS ENUM ('unverified', 'passed', 'failed')"""
    )
    op.execute(
        """CREATE TYPE cwom_doctrine_type AS ENUM (
            'principle', 'policy', 'procedure', 'heuristic', 'pattern'
        )"""
    )
    op.execute(
        """CREATE TYPE cwom_doctrine_priority AS ENUM ('must', 'should', 'may')"""
    )
    op.execute(
        """CREATE TYPE cwom_visibility AS ENUM ('public', 'private', 'internal')"""
    )
    op.execute(
        """CREATE TYPE cwom_actor_kind AS ENUM ('human', 'agent', 'system')"""
    )
    op.execute(
        """CREATE TYPE cwom_constraint_scope AS ENUM ('personal', 'repo', 'org', 'system', 'run')"""
    )

    # ==========================================================================
    # Create CWOM Repos Table
    # ==========================================================================
    op.create_table(
        "cwom_repos",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="Repo"),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(256), nullable=False),
        sa.Column("default_branch", sa.String(128), nullable=False, server_default="main"),
        sa.Column(
            "visibility",
            sa.Enum("public", "private", "internal", name="cwom_visibility"),
            nullable=False,
            server_default="private",
        ),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("owners", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("policy", sa.JSON(), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_cwom_repos_slug"),
    )
    op.create_index("ix_cwom_repos_name", "cwom_repos", ["name"])
    op.create_index("ix_cwom_repos_slug", "cwom_repos", ["slug"])
    op.create_index("ix_cwom_repos_visibility", "cwom_repos", ["visibility"])
    op.create_index("ix_cwom_repos_created_at", "cwom_repos", ["created_at"])

    # ==========================================================================
    # Create CWOM Constraint Snapshots Table (needed before Issues for FK)
    # ==========================================================================
    op.create_table(
        "cwom_constraint_snapshots",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="ConstraintSnapshot"),
        sa.Column(
            "scope",
            sa.Enum("personal", "repo", "org", "system", "run", name="cwom_constraint_scope"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "owner_kind",
            sa.Enum("human", "agent", "system", name="cwom_actor_kind"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("owner_display", sa.String(256), nullable=True),
        sa.Column("constraints", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cwom_constraint_snapshots_scope", "cwom_constraint_snapshots", ["scope"])
    op.create_index("ix_cwom_constraint_snapshots_captured_at", "cwom_constraint_snapshots", ["captured_at"])
    op.create_index("ix_cwom_constraint_snapshots_owner", "cwom_constraint_snapshots", ["owner_kind", "owner_id"])

    # ==========================================================================
    # Create CWOM Doctrine Refs Table (needed before Issues for FK)
    # ==========================================================================
    op.create_table(
        "cwom_doctrine_refs",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="DoctrineRef"),
        sa.Column("namespace", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column(
            "type",
            sa.Enum("principle", "policy", "procedure", "heuristic", "pattern", name="cwom_doctrine_type"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("must", "should", "may", name="cwom_doctrine_priority"),
            nullable=False,
            server_default="should",
        ),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("applicability", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "name", "version", name="uq_doctrine_ref_nv"),
    )
    op.create_index("ix_cwom_doctrine_refs_namespace", "cwom_doctrine_refs", ["namespace"])
    op.create_index("ix_cwom_doctrine_refs_name", "cwom_doctrine_refs", ["name"])
    op.create_index("ix_cwom_doctrine_refs_version", "cwom_doctrine_refs", ["version"])
    op.create_index("ix_cwom_doctrine_refs_type", "cwom_doctrine_refs", ["type"])
    op.create_index("ix_cwom_doctrine_refs_namespace_name", "cwom_doctrine_refs", ["namespace", "name"])
    op.create_index("ix_cwom_doctrine_refs_type_priority", "cwom_doctrine_refs", ["type", "priority"])
    op.create_index("ix_cwom_doctrine_refs_created_at", "cwom_doctrine_refs", ["created_at"])

    # ==========================================================================
    # Create CWOM Issues Table
    # ==========================================================================
    op.create_table(
        "cwom_issues",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="Issue"),
        sa.Column("repo_id", sa.String(128), sa.ForeignKey("cwom_repos.id"), nullable=False),
        sa.Column("repo_kind", sa.String(20), nullable=False, server_default="Repo"),
        sa.Column("repo_role", sa.String(64), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "type",
            sa.Enum("feature", "bug", "chore", "research", "ops", "doc", "incident", name="cwom_issue_type"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("P0", "P1", "P2", "P3", "P4", name="cwom_priority"),
            nullable=False,
            server_default="P2",
        ),
        sa.Column(
            "status",
            sa.Enum("planned", "ready", "running", "blocked", "done", "failed", "canceled", name="cwom_status"),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("assignees", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("watchers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("acceptance", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("relationships", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("runs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cwom_issues_repo_id", "cwom_issues", ["repo_id"])
    op.create_index("ix_cwom_issues_type", "cwom_issues", ["type"])
    op.create_index("ix_cwom_issues_priority", "cwom_issues", ["priority"])
    op.create_index("ix_cwom_issues_status", "cwom_issues", ["status"])
    op.create_index("ix_cwom_issues_type_status", "cwom_issues", ["type", "status"])
    op.create_index("ix_cwom_issues_priority_status", "cwom_issues", ["priority", "status"])
    op.create_index("ix_cwom_issues_created_at", "cwom_issues", ["created_at"])

    # ==========================================================================
    # Create CWOM Context Packets Table
    # ==========================================================================
    op.create_table(
        "cwom_context_packets",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="ContextPacket"),
        sa.Column("for_issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), nullable=False),
        sa.Column("for_issue_kind", sa.String(20), nullable=False, server_default="Issue"),
        sa.Column("for_issue_role", sa.String(64), nullable=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("assumptions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("open_questions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("constraint_snapshot_id", sa.String(128), sa.ForeignKey("cwom_constraint_snapshots.id"), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cwom_context_packets_for_issue_id", "cwom_context_packets", ["for_issue_id"])
    op.create_index("ix_cwom_context_packets_version", "cwom_context_packets", ["version"])
    op.create_index("ix_cwom_context_packets_created_at", "cwom_context_packets", ["created_at"])

    # ==========================================================================
    # Create CWOM Runs Table
    # ==========================================================================
    op.create_table(
        "cwom_runs",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="Run"),
        sa.Column("for_issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), nullable=False),
        sa.Column("for_issue_kind", sa.String(20), nullable=False, server_default="Issue"),
        sa.Column("for_issue_role", sa.String(64), nullable=True),
        sa.Column("repo_id", sa.String(128), sa.ForeignKey("cwom_repos.id"), nullable=False),
        sa.Column("repo_kind", sa.String(20), nullable=False, server_default="Repo"),
        sa.Column("repo_role", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("planned", "ready", "running", "blocked", "done", "failed", "canceled", name="cwom_status"),
            nullable=False,
            server_default="planned",
        ),
        sa.Column(
            "mode",
            sa.Enum("human", "agent", "hybrid", "system", name="cwom_run_mode"),
            nullable=False,
        ),
        sa.Column("executor", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("constraint_snapshot_id", sa.String(128), sa.ForeignKey("cwom_constraint_snapshots.id"), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("telemetry", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("cost", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("outputs", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("failure", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cwom_runs_for_issue_id", "cwom_runs", ["for_issue_id"])
    op.create_index("ix_cwom_runs_repo_id", "cwom_runs", ["repo_id"])
    op.create_index("ix_cwom_runs_status", "cwom_runs", ["status"])
    op.create_index("ix_cwom_runs_mode", "cwom_runs", ["mode"])
    op.create_index("ix_cwom_runs_status_mode", "cwom_runs", ["status", "mode"])
    op.create_index("ix_cwom_runs_created_at", "cwom_runs", ["created_at"])

    # ==========================================================================
    # Create CWOM Artifacts Table
    # ==========================================================================
    op.create_table(
        "cwom_artifacts",
        sa.Column("id", sa.String(128), nullable=False, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="Artifact"),
        sa.Column("produced_by_id", sa.String(128), sa.ForeignKey("cwom_runs.id"), nullable=False),
        sa.Column("produced_by_kind", sa.String(20), nullable=False, server_default="Run"),
        sa.Column("produced_by_role", sa.String(64), nullable=True),
        sa.Column("for_issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), nullable=False),
        sa.Column("for_issue_kind", sa.String(20), nullable=False, server_default="Issue"),
        sa.Column("for_issue_role", sa.String(64), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "code_patch", "commit", "pr", "build", "container_image",
                "doc", "report", "dataset", "log", "trace", "binary", "link",
                name="cwom_artifact_type",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("uri", sa.String(2000), nullable=False),
        sa.Column("digest", sa.String(128), nullable=True),
        sa.Column("media_type", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("preview", sa.Text(), nullable=True),
        sa.Column("verification", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cwom_artifacts_produced_by_id", "cwom_artifacts", ["produced_by_id"])
    op.create_index("ix_cwom_artifacts_for_issue_id", "cwom_artifacts", ["for_issue_id"])
    op.create_index("ix_cwom_artifacts_type", "cwom_artifacts", ["type"])
    op.create_index("ix_cwom_artifacts_digest", "cwom_artifacts", ["digest"])
    op.create_index("ix_cwom_artifacts_created_at", "cwom_artifacts", ["created_at"])

    # ==========================================================================
    # Create Join Tables for Many-to-Many Relationships
    # ==========================================================================

    # Issue <-> ContextPacket
    op.create_table(
        "cwom_issue_context_packets",
        sa.Column("issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), primary_key=True),
        sa.Column("context_packet_id", sa.String(128), sa.ForeignKey("cwom_context_packets.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Issue <-> DoctrineRef
    op.create_table(
        "cwom_issue_doctrine_refs",
        sa.Column("issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), primary_key=True),
        sa.Column("doctrine_ref_id", sa.String(128), sa.ForeignKey("cwom_doctrine_refs.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Issue <-> ConstraintSnapshot
    op.create_table(
        "cwom_issue_constraint_snapshots",
        sa.Column("issue_id", sa.String(128), sa.ForeignKey("cwom_issues.id"), primary_key=True),
        sa.Column("constraint_snapshot_id", sa.String(128), sa.ForeignKey("cwom_constraint_snapshots.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Run <-> ContextPacket
    op.create_table(
        "cwom_run_context_packets",
        sa.Column("run_id", sa.String(128), sa.ForeignKey("cwom_runs.id"), primary_key=True),
        sa.Column("context_packet_id", sa.String(128), sa.ForeignKey("cwom_context_packets.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Run <-> DoctrineRef
    op.create_table(
        "cwom_run_doctrine_refs",
        sa.Column("run_id", sa.String(128), sa.ForeignKey("cwom_runs.id"), primary_key=True),
        sa.Column("doctrine_ref_id", sa.String(128), sa.ForeignKey("cwom_doctrine_refs.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ContextPacket <-> DoctrineRef
    op.create_table(
        "cwom_context_packet_doctrine_refs",
        sa.Column("context_packet_id", sa.String(128), sa.ForeignKey("cwom_context_packets.id"), primary_key=True),
        sa.Column("doctrine_ref_id", sa.String(128), sa.ForeignKey("cwom_doctrine_refs.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop join tables
    op.drop_table("cwom_context_packet_doctrine_refs")
    op.drop_table("cwom_run_doctrine_refs")
    op.drop_table("cwom_run_context_packets")
    op.drop_table("cwom_issue_constraint_snapshots")
    op.drop_table("cwom_issue_doctrine_refs")
    op.drop_table("cwom_issue_context_packets")

    # Drop main tables (reverse order of creation due to FKs)
    op.drop_table("cwom_artifacts")
    op.drop_table("cwom_runs")
    op.drop_table("cwom_context_packets")
    op.drop_table("cwom_issues")
    op.drop_table("cwom_doctrine_refs")
    op.drop_table("cwom_constraint_snapshots")
    op.drop_table("cwom_repos")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS cwom_constraint_scope")
    op.execute("DROP TYPE IF EXISTS cwom_actor_kind")
    op.execute("DROP TYPE IF EXISTS cwom_visibility")
    op.execute("DROP TYPE IF EXISTS cwom_doctrine_priority")
    op.execute("DROP TYPE IF EXISTS cwom_doctrine_type")
    op.execute("DROP TYPE IF EXISTS cwom_verification_status")
    op.execute("DROP TYPE IF EXISTS cwom_artifact_type")
    op.execute("DROP TYPE IF EXISTS cwom_run_mode")
    op.execute("DROP TYPE IF EXISTS cwom_priority")
    op.execute("DROP TYPE IF EXISTS cwom_issue_type")
    op.execute("DROP TYPE IF EXISTS cwom_status")
    op.execute("DROP TYPE IF EXISTS cwom_object_kind")
