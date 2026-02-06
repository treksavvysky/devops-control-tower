#!/bin/bash
# Verify migrations apply cleanly on fresh SQLite DB
#
# This script:
# 1. Creates a fresh SQLite database
# 2. Runs all migrations (upgrade head)
# 3. Verifies all 22 expected tables exist
# 4. Tests downgrade one step and re-upgrade
# 5. Verifies alembic history has no forks
# 6. Cleans up
#
# Exit codes:
#   0 - All checks passed
#   1 - Migration or verification failure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_FILE="$PROJECT_DIR/test_fresh_migration.db"

# Ensure we run from project root (alembic.ini lives there)
cd "$PROJECT_DIR"

# Clean slate
rm -f "$DB_FILE"
export DATABASE_URL="sqlite:///$DB_FILE"

cleanup() {
    rm -f "$DB_FILE"
}
trap cleanup EXIT

echo "=== Phase 4: Fresh DB Verification ==="
echo ""
echo "Project dir: $PROJECT_DIR"
echo "Database:    $DATABASE_URL"
echo ""

# ── Step 1: Upgrade ─────────────────────────────────────────────
echo "1/5  Running 'alembic upgrade head' on fresh DB..."
alembic upgrade head
echo "     OK"

# ── Step 2: Verify tables ───────────────────────────────────────
echo ""
echo "2/5  Verifying all required tables exist..."
python3 -c "
import sys
from sqlalchemy import create_engine, inspect

engine = create_engine('$DATABASE_URL')
tables = set(inspect(engine).get_table_names())

# All 22 application tables + alembic_version
required = {
    # Core tables (a1b2c3d4e5f6)
    'events', 'workflows', 'agents',
    # Task table (b2f6a732d137)
    'tasks',
    # CWOM entity tables (c3e8f9a21b4d)
    'cwom_repos', 'cwom_issues', 'cwom_context_packets',
    'cwom_constraint_snapshots', 'cwom_doctrine_refs',
    'cwom_runs', 'cwom_artifacts',
    # CWOM join tables (c3e8f9a21b4d)
    'cwom_issue_context_packets', 'cwom_issue_doctrine_refs',
    'cwom_issue_constraint_snapshots', 'cwom_run_context_packets',
    'cwom_run_doctrine_refs', 'cwom_context_packet_doctrine_refs',
    # Sprint-0 tables (e5f6a7b8c9d0)
    'jobs', 'artifacts',
    # Audit log (f7a8b9c0d1e2)
    'audit_log',
    # Evidence packs (i0d1e2f3a4b5)
    'cwom_evidence_packs',
    # Review decisions (j1e2f3a4b5c6)
    'cwom_review_decisions',
    # Alembic tracking
    'alembic_version',
}

missing = sorted(required - tables)
extra = sorted(tables - required)

if missing:
    print(f'FAIL: Missing tables: {missing}')
    sys.exit(1)

print(f'     PASS: All {len(required)} required tables present ({len(required) - 1} app + alembic_version)')
if extra:
    print(f'     NOTE: Extra tables found: {extra}')
"

# ── Step 3: Downgrade ───────────────────────────────────────────
echo ""
echo "3/5  Testing 'alembic downgrade -1'..."
alembic downgrade -1
echo "     OK"

# ── Step 4: Re-upgrade ──────────────────────────────────────────
echo ""
echo "4/5  Re-upgrading to head..."
alembic upgrade head
echo "     OK"

# ── Step 5: History check (no forks) ────────────────────────────
echo ""
echo "5/5  Verifying migration history has no forks..."
python3 -c "
import sys
from alembic.config import Config
from alembic.script import ScriptDirectory

cfg = Config('alembic.ini')
scripts = ScriptDirectory.from_config(cfg)

# Walk the full chain from base to heads
heads = scripts.get_heads()
if len(heads) != 1:
    print(f'FAIL: Expected 1 head, found {len(heads)}: {heads}')
    sys.exit(1)

# Walk from head back to base, count revisions
count = 0
current = heads[0]
while current is not None:
    rev = scripts.get_revision(current)
    count += 1
    # down_revision can be None (base) or a string
    current = rev.down_revision
    if isinstance(current, tuple):
        print(f'FAIL: Branching detected at {rev.revision}')
        sys.exit(1)

print(f'     PASS: Linear chain of {count} migrations, 1 head')
"

echo ""
echo "=== SUCCESS: Fresh DB verification passed ==="
