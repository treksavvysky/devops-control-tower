#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."

# Use Python to wait for PostgreSQL since it uses the same library as the app
python3 << 'PYTHON_SCRIPT'
import os
import sys
import time
from urllib.parse import urlparse

database_url = os.environ.get('DATABASE_URL', '')

if database_url:
    # Parse DATABASE_URL
    parsed = urlparse(database_url)
    host = parsed.hostname or 'postgres'
    port = parsed.port or 5432
    user = parsed.username or 'devops'
    password = parsed.password or 'devops'
    dbname = parsed.path[1:] if parsed.path else 'devops_control_tower'
else:
    host = os.environ.get('POSTGRES_HOST', 'postgres')
    port = int(os.environ.get('POSTGRES_PORT', 5432))
    user = os.environ.get('POSTGRES_USER', 'devops')
    password = os.environ.get('POSTGRES_PASSWORD', 'devops')
    dbname = os.environ.get('POSTGRES_DB', 'devops_control_tower')

max_retries = 30
retry_interval = 2

for attempt in range(max_retries):
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            connect_timeout=5
        )
        conn.close()
        print(f"PostgreSQL is ready! (attempt {attempt + 1})")
        # Extra small delay for stability
        time.sleep(1)
        sys.exit(0)
    except Exception as e:
        print(f"Waiting for PostgreSQL... (attempt {attempt + 1}/{max_retries}): {e}")
        time.sleep(retry_interval)

print("ERROR: PostgreSQL did not become ready in time")
sys.exit(1)
PYTHON_SCRIPT

echo "Starting DevOps Control Tower..."
exec python -m devops_control_tower.main
