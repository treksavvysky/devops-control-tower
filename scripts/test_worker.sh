#!/bin/bash
#
# Practical Test Plan: Worker (Step 2)
#
# Tests the full worker flow: queued task → Worker → trace folder
#
# Usage:
#   ./scripts/test_worker.sh [BASE_URL]
#
# Prerequisites:
#   - Server running (python -m devops_control_tower.main)
#   - Database migrated (alembic upgrade head)
#   - jq installed (for JSON parsing)
#   - Write access to trace directory

set -e

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0
TESTS_RUN=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Unique suffix to avoid idempotency collisions across runs
RUN_ID=$(date +%s)

# Trace root (should match JCT_TRACE_ROOT or default)
TRACE_ROOT="${JCT_TRACE_ROOT:-file:///var/lib/jct/runs}"
# Extract path from file:// URI
TRACE_PATH="${TRACE_ROOT#file://}"

echo "=============================================="
echo "  Worker (Step 2) - Practical Test Plan"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Run ID: $RUN_ID"
echo "Trace root: $TRACE_ROOT"
echo "Trace path: $TRACE_PATH"
echo ""

# Check prerequisites
check_prereqs() {
    echo -n "Checking prerequisites... "

    if ! command -v jq &> /dev/null; then
        echo -e "${RED}FAIL${NC} - jq not installed"
        exit 1
    fi

    if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
        echo -e "${RED}FAIL${NC} - Server not running at $BASE_URL"
        echo "Start with: python -m devops_control_tower.main"
        exit 1
    fi

    # Create trace directory if needed
    if [[ "$TRACE_PATH" != "" ]] && [[ ! -d "$TRACE_PATH" ]]; then
        echo ""
        echo -n "Creating trace directory $TRACE_PATH... "
        mkdir -p "$TRACE_PATH" 2>/dev/null || {
            echo -e "${YELLOW}WARN${NC} - Cannot create $TRACE_PATH (may need sudo)"
            echo "  Creating in /tmp instead..."
            export JCT_TRACE_ROOT="file:///tmp/jct-test-runs"
            TRACE_ROOT="$JCT_TRACE_ROOT"
            TRACE_PATH="/tmp/jct-test-runs"
            mkdir -p "$TRACE_PATH"
        }
    fi

    echo -e "${GREEN}OK${NC}"
}

# Test helper
run_test() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    local validation="$4"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo ""
    echo "--- Test $TESTS_RUN: $name ---"

    if [ "$actual" != "$expected" ]; then
        echo -e "${RED}FAIL${NC} - Expected '$expected', got '$actual'"
        FAIL=$((FAIL + 1))
        return 1
    fi

    if [ -n "$validation" ]; then
        if ! eval "$validation"; then
            echo -e "${RED}FAIL${NC} - Validation failed"
            FAIL=$((FAIL + 1))
            return 1
        fi
    fi

    echo -e "${GREEN}PASS${NC}"
    PASS=$((PASS + 1))
    return 0
}

# Store task_id from Test 1 for later tests
TASK_ID=""
CWOM_RUN_ID=""

check_prereqs

#############################################
# Test 1: Create a task with CWOM
#############################################
echo ""
echo "=== Test 1: Create Task with CWOM ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue?create_cwom=true" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: worker-test-$RUN_ID" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"worker-test-$RUN_ID\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"operator\", \"label\": \"Test Operator\"},
    \"objective\": \"Test task for worker validation - should be processed by stub executor\",
    \"operation\": \"code_change\",
    \"target\": {\"repo\": \"testorg/worker-test\", \"ref\": \"main\", \"path\": \"src\"},
    \"constraints\": {\"time_budget_seconds\": 60},
    \"acceptance_criteria\": [\"Task completes without error\"],
    \"evidence_requirements\": [\"Trace folder exists\", \"manifest.json present\"]
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

TASK_ID=$(echo "$BODY" | jq -r '.task_id // empty')
CWOM_ISSUE_ID=$(echo "$BODY" | jq -r '.cwom.issue_id // empty')

run_test "Create Task with CWOM" "201" "$HTTP_CODE" \
    "[ -n '$TASK_ID' ] && [ -n '$CWOM_ISSUE_ID' ]"

echo "  Task ID: $TASK_ID"
echo "  CWOM Issue ID: $CWOM_ISSUE_ID"

#############################################
# Test 2: Verify task is queued
#############################################
echo ""
echo "=== Test 2: Verify Task is Queued ==="

RESPONSE=$(curl -s "$BASE_URL/tasks/$TASK_ID")
TASK_STATUS=$(echo "$RESPONSE" | jq -r '.status // empty')

run_test "Task status is queued" "queued" "$TASK_STATUS"

#############################################
# Test 3: Run worker for one cycle
#############################################
echo ""
echo "=== Test 3: Run Worker (Single Cycle) ==="

# Run worker in background, let it process one task, then stop
echo "Starting worker..."

# Set trace root for this test
export JCT_TRACE_ROOT="$TRACE_ROOT"

# Run worker with timeout (5 seconds should be enough for stub)
timeout 10s python3 -m devops_control_tower.worker --poll-interval 1 &
WORKER_PID=$!

# Wait for task to be processed
echo "Waiting for task to be processed..."
sleep 6

# Kill worker
kill $WORKER_PID 2>/dev/null || true
wait $WORKER_PID 2>/dev/null || true

echo "Worker stopped."

#############################################
# Test 4: Verify task is completed
#############################################
echo ""
echo "=== Test 4: Verify Task Completed ==="

RESPONSE=$(curl -s "$BASE_URL/tasks/$TASK_ID")
TASK_STATUS=$(echo "$RESPONSE" | jq -r '.status // empty')
TRACE_PATH_RESULT=$(echo "$RESPONSE" | jq -r '.trace_path // empty')

run_test "Task status is completed" "completed" "$TASK_STATUS"

echo "  Trace path: $TRACE_PATH_RESULT"

#############################################
# Test 5: Verify CWOM Run created
#############################################
echo ""
echo "=== Test 5: Verify CWOM Run Created ==="

# Get runs for the issue
RESPONSE=$(curl -s "$BASE_URL/cwom/runs")
RUN_FOR_ISSUE=$(echo "$RESPONSE" | jq -r --arg issue_id "$CWOM_ISSUE_ID" '.[] | select(.for_issue.id == $issue_id) | .id' | head -1)

if [ -n "$RUN_FOR_ISSUE" ]; then
    CWOM_RUN_ID="$RUN_FOR_ISSUE"
    RESPONSE=$(curl -s "$BASE_URL/cwom/runs/$CWOM_RUN_ID")
    RUN_STATUS=$(echo "$RESPONSE" | jq -r '.status // empty')
    RUN_ARTIFACT_URI=$(echo "$RESPONSE" | jq -r '.artifact_root_uri // empty')

    run_test "CWOM Run status is done" "done" "$RUN_STATUS"

    echo "  Run ID: $CWOM_RUN_ID"
    echo "  Run artifact URI: $RUN_ARTIFACT_URI"
else
    echo -e "${RED}FAIL${NC} - No CWOM Run found for issue $CWOM_ISSUE_ID"
    FAIL=$((FAIL + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
fi

#############################################
# Test 6: Verify trace folder structure
#############################################
echo ""
echo "=== Test 6: Verify Trace Folder Structure ==="

# Extract path from trace URI
if [ -n "$TRACE_PATH_RESULT" ]; then
    TRACE_DIR="${TRACE_PATH_RESULT#file://}"

    if [ -d "$TRACE_DIR" ]; then
        HAS_MANIFEST=$([ -f "$TRACE_DIR/manifest.json" ] && echo "true" || echo "false")
        HAS_EVENTS=$([ -f "$TRACE_DIR/events.jsonl" ] && echo "true" || echo "false")
        HAS_TRACE_LOG=$([ -f "$TRACE_DIR/trace.log" ] && echo "true" || echo "false")
        HAS_ARTIFACTS=$([ -d "$TRACE_DIR/artifacts" ] && echo "true" || echo "false")

        run_test "Trace folder has manifest.json" "true" "$HAS_MANIFEST"

        echo "  manifest.json: $HAS_MANIFEST"
        echo "  events.jsonl: $HAS_EVENTS"
        echo "  trace.log: $HAS_TRACE_LOG"
        echo "  artifacts/: $HAS_ARTIFACTS"

        # Show manifest content
        if [ "$HAS_MANIFEST" = "true" ]; then
            echo ""
            echo "  Manifest content:"
            jq '.' "$TRACE_DIR/manifest.json" | sed 's/^/    /'
        fi
    else
        echo -e "${YELLOW}SKIP${NC} - Trace directory not found: $TRACE_DIR"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No trace path in task"
fi

#############################################
# Test 7: Verify artifact created
#############################################
echo ""
echo "=== Test 7: Verify Artifact in Trace Folder ==="

if [ -n "$TRACE_DIR" ] && [ -d "$TRACE_DIR/artifacts" ]; then
    ARTIFACT_FILE="$TRACE_DIR/artifacts/output.md"
    if [ -f "$ARTIFACT_FILE" ]; then
        run_test "Artifact output.md exists" "true" "true"
        echo "  First 5 lines of output.md:"
        head -5 "$ARTIFACT_FILE" | sed 's/^/    /'
    else
        echo -e "${YELLOW}SKIP${NC} - No artifact file found"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No artifacts directory"
fi

#############################################
# Test 8: Verify CWOM Artifact record
#############################################
echo ""
echo "=== Test 8: Verify CWOM Artifact Record ==="

if [ -n "$CWOM_RUN_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/artifacts")
    ARTIFACT_FOR_RUN=$(echo "$RESPONSE" | jq -r --arg run_id "$CWOM_RUN_ID" '.[] | select(.produced_by.id == $run_id) | .id' | head -1)

    if [ -n "$ARTIFACT_FOR_RUN" ]; then
        RESPONSE=$(curl -s "$BASE_URL/cwom/artifacts")
        ARTIFACT=$(echo "$RESPONSE" | jq -r --arg id "$ARTIFACT_FOR_RUN" '.[] | select(.id == $id)')
        ARTIFACT_TYPE=$(echo "$ARTIFACT" | jq -r '.type // empty')
        ARTIFACT_URI=$(echo "$ARTIFACT" | jq -r '.uri // empty')

        run_test "CWOM Artifact exists" "true" "$([ -n '$ARTIFACT_FOR_RUN' ] && echo 'true' || echo 'false')"

        echo "  Artifact ID: $ARTIFACT_FOR_RUN"
        echo "  Type: $ARTIFACT_TYPE"
        echo "  URI: $ARTIFACT_URI"
    else
        echo -e "${YELLOW}SKIP${NC} - No CWOM Artifact found for run"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No CWOM Run ID"
fi

#############################################
# Test 9: Verify Issue status updated
#############################################
echo ""
echo "=== Test 9: Verify Issue Status Updated ==="

if [ -n "$CWOM_ISSUE_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/issues/$CWOM_ISSUE_ID")
    ISSUE_STATUS=$(echo "$RESPONSE" | jq -r '.status // empty')

    run_test "Issue status is done" "done" "$ISSUE_STATUS"
else
    echo -e "${YELLOW}SKIP${NC} - No CWOM Issue ID"
fi

#############################################
# Summary
#############################################
echo ""
echo "=============================================="
echo "  SUMMARY"
echo "=============================================="
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo "Total:  $TESTS_RUN"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
