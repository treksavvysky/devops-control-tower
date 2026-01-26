#!/bin/bash
# Verify migrations apply cleanly on fresh SQLite DB
#
# This script:
# 1. Creates a fresh SQLite database
# 2. Runs all migrations
# 3. Verifies all expected tables exist
# 4. Tests downgrade works
# 5. Cleans up

set -e

echo "=== CWOM Fresh DB Verification Script ==="
echo ""

# Set up temp database
export DATABASE_URL="sqlite:///./test_fresh_migration.db"
rm -f test_fresh_migration.db

echo "1. Running migrations on fresh DB..."
alembic upgrade head

echo ""
echo "2. Verifying tables exist..."
python3 -c "
from devops_control_tower.db.base import get_engine
from sqlalchemy import inspect

engine = get_engine()
tables = set(inspect(engine).get_table_names())

# Expected tables after all migrations
required = {
    # Core tables (a1b2c3d4e5f6)
    'events', 'workflows', 'agents',
    # Task table (b2f6a732d137)
    'tasks',
    # CWOM tables (c3e8f9a21b4d)
    'cwom_repos', 'cwom_issues', 'cwom_context_packets',
    'cwom_constraint_snapshots', 'cwom_doctrine_refs',
    'cwom_runs', 'cwom_artifacts',
    # CWOM join tables
    'cwom_issue_context_packets', 'cwom_issue_doctrine_refs',
    'cwom_issue_constraint_snapshots', 'cwom_run_context_packets',
    'cwom_run_doctrine_refs', 'cwom_context_packet_doctrine_refs',
    # Sprint-0 tables (e5f6a7b8c9d0)
    'jobs', 'artifacts',
    # Alembic version tracking
    'alembic_version',
}

missing = required - tables
extra = tables - required

if missing:
    print(f'FAIL: Missing tables: {missing}')
    exit(1)

if extra:
    print(f'WARNING: Extra tables found: {extra}')

print(f'PASS: All {len(required)} required tables present')
"

echo ""
echo "3. Testing downgrade (one step)..."
alembic downgrade -1

echo ""
echo "4. Upgrade back to head..."
alembic upgrade head

echo ""
echo "5. Verifying alembic history is coherent..."
alembic history

echo ""
echo "=== SUCCESS: Fresh DB verification passed ==="

# Cleanup
rm -f test_fresh_migration.db
echo ""
echo "Temp database cleaned up."
