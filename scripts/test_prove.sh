#!/bin/bash
#
# Practical Test Plan: Prove (Step 4)
#
# Tests the proof flow: Run → Evidence Pack → Verdict
#
# Usage:
#   ./scripts/test_prove.sh [BASE_URL]
#
# Prerequisites:
#   - Server running (python -m devops_control_tower.main)
#   - Database migrated (alembic upgrade head)
#   - jq installed (for JSON parsing)

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

# Unique suffix for this test run
RUN_ID=$(date +%s)

# Trace root
TRACE_ROOT="${JCT_TRACE_ROOT:-file:///tmp/jct-test-runs}"
TRACE_PATH="${TRACE_ROOT#file://}"

echo "=============================================="
echo "  Prove (Step 4) - Practical Test Plan"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Run ID: $RUN_ID"
echo "Trace root: $TRACE_ROOT"
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
        exit 1
    fi

    mkdir -p "$TRACE_PATH"

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

# Store IDs
TASK_ID=""
CWOM_RUN_ID=""
EVIDENCE_PACK_ID=""

check_prereqs

#############################################
# Test 1: Create Task with acceptance criteria
#############################################
echo ""
echo "=== Test 1: Create Task with Acceptance Criteria ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue?create_cwom=true" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: prove-test-$RUN_ID" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"prove-test-$RUN_ID\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"tester\"},
    \"objective\": \"Test task for prove validation\",
    \"operation\": \"code_change\",
    \"target\": {\"repo\": \"testorg/prove-test\", \"ref\": \"main\"},
    \"constraints\": {\"time_budget_seconds\": 60},
    \"acceptance_criteria\": [
      \"Task completes successfully\",
      \"Output file is generated\",
      \"No errors in trace log\"
    ],
    \"evidence_requirements\": [
      \"Stub Output\"
    ]
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

TASK_ID=$(echo "$BODY" | jq -r '.task_id // empty')
CWOM_ISSUE_ID=$(echo "$BODY" | jq -r '.cwom.issue_id // empty')

run_test "Create Task with Acceptance Criteria" "201" "$HTTP_CODE" \
    "[ -n '$TASK_ID' ]"

echo "  Task ID: $TASK_ID"
echo "  Issue ID: $CWOM_ISSUE_ID"

#############################################
# Test 2: Run worker to process and prove
#############################################
echo ""
echo "=== Test 2: Run Worker (with Prove step) ==="

export JCT_TRACE_ROOT="$TRACE_ROOT"

# Run worker
echo "Starting worker..."
timeout 15s python3 -m devops_control_tower.worker --poll-interval 1 &
WORKER_PID=$!

sleep 8

kill $WORKER_PID 2>/dev/null || true
wait $WORKER_PID 2>/dev/null || true

echo "Worker stopped."

#############################################
# Test 3: Verify task completed
#############################################
echo ""
echo "=== Test 3: Verify Task Completed ==="

RESPONSE=$(curl -s "$BASE_URL/tasks/$TASK_ID")
TASK_STATUS=$(echo "$RESPONSE" | jq -r '.status // empty')

run_test "Task completed" "completed" "$TASK_STATUS"

#############################################
# Test 4: Verify CWOM Run has evidence pack
#############################################
echo ""
echo "=== Test 4: Get CWOM Run ==="

# Get runs for the issue
RESPONSE=$(curl -s "$BASE_URL/cwom/runs")
CWOM_RUN_ID=$(echo "$RESPONSE" | jq -r --arg issue_id "$CWOM_ISSUE_ID" '.[] | select(.for_issue.id == $issue_id) | .id' | head -1)

if [ -n "$CWOM_RUN_ID" ]; then
    run_test "CWOM Run exists" "true" "true"
    echo "  Run ID: $CWOM_RUN_ID"
else
    echo -e "${RED}FAIL${NC} - No CWOM Run found"
    FAIL=$((FAIL + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
fi

#############################################
# Test 5: Verify Evidence Pack created
#############################################
echo ""
echo "=== Test 5: Verify Evidence Pack Created ==="

if [ -n "$CWOM_RUN_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/runs/$CWOM_RUN_ID/evidence-pack")
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/cwom/runs/$CWOM_RUN_ID/evidence-pack")

    if [ "$HTTP_CODE" = "200" ]; then
        EVIDENCE_PACK_ID=$(echo "$RESPONSE" | jq -r '.id // empty')
        VERDICT=$(echo "$RESPONSE" | jq -r '.verdict // empty')
        VERDICT_REASON=$(echo "$RESPONSE" | jq -r '.verdict_reason // empty')

        run_test "Evidence Pack exists" "200" "$HTTP_CODE"

        echo "  Evidence Pack ID: $EVIDENCE_PACK_ID"
        echo "  Verdict: $VERDICT"
        echo "  Reason: $VERDICT_REASON"
    else
        echo -e "${RED}FAIL${NC} - Evidence Pack not found (HTTP $HTTP_CODE)"
        FAIL=$((FAIL + 1))
        TESTS_RUN=$((TESTS_RUN + 1))
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No Run ID"
fi

#############################################
# Test 6: Verify verdict is pass
#############################################
echo ""
echo "=== Test 6: Verify Verdict is Pass ==="

if [ -n "$EVIDENCE_PACK_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/evidence-packs/$EVIDENCE_PACK_ID")
    VERDICT=$(echo "$RESPONSE" | jq -r '.verdict // empty')

    run_test "Verdict is pass" "pass" "$VERDICT"

    # Show check counts
    CHECKS_PASSED=$(echo "$RESPONSE" | jq -r '.checks_passed // 0')
    CHECKS_FAILED=$(echo "$RESPONSE" | jq -r '.checks_failed // 0')
    CHECKS_SKIPPED=$(echo "$RESPONSE" | jq -r '.checks_skipped // 0')

    echo "  Checks passed: $CHECKS_PASSED"
    echo "  Checks failed: $CHECKS_FAILED"
    echo "  Checks skipped: $CHECKS_SKIPPED"
else
    echo -e "${YELLOW}SKIP${NC} - No Evidence Pack ID"
fi

#############################################
# Test 7: Verify evidence folder in trace
#############################################
echo ""
echo "=== Test 7: Verify Evidence Folder ==="

if [ -n "$EVIDENCE_PACK_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/evidence-packs/$EVIDENCE_PACK_ID")
    EVIDENCE_URI=$(echo "$RESPONSE" | jq -r '.evidence_uri // empty')

    if [ -n "$EVIDENCE_URI" ]; then
        EVIDENCE_PATH="${EVIDENCE_URI#file://}"
        EVIDENCE_PATH="${EVIDENCE_PATH%/}"  # Remove trailing slash

        if [ -d "$EVIDENCE_PATH" ]; then
            HAS_VERDICT=$([ -f "$EVIDENCE_PATH/verdict.json" ] && echo "true" || echo "false")
            HAS_COLLECTED=$([ -f "$EVIDENCE_PATH/collected.json" ] && echo "true" || echo "false")
            HAS_CRITERIA=$([ -d "$EVIDENCE_PATH/criteria" ] && echo "true" || echo "false")

            run_test "Evidence folder has verdict.json" "true" "$HAS_VERDICT"

            echo "  verdict.json: $HAS_VERDICT"
            echo "  collected.json: $HAS_COLLECTED"
            echo "  criteria/: $HAS_CRITERIA"

            if [ "$HAS_VERDICT" = "true" ]; then
                echo ""
                echo "  Verdict content:"
                jq '.' "$EVIDENCE_PATH/verdict.json" | sed 's/^/    /'
            fi
        else
            echo -e "${YELLOW}SKIP${NC} - Evidence path not found: $EVIDENCE_PATH"
        fi
    else
        echo -e "${YELLOW}SKIP${NC} - No evidence_uri in pack"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No Evidence Pack"
fi

#############################################
# Test 8: Verify criteria results
#############################################
echo ""
echo "=== Test 8: Verify Criteria Results ==="

if [ -n "$EVIDENCE_PACK_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/evidence-packs/$EVIDENCE_PACK_ID")
    CRITERIA_COUNT=$(echo "$RESPONSE" | jq '.criteria_results | length')

    if [ "$CRITERIA_COUNT" -gt 0 ]; then
        run_test "Criteria results present" "true" "$([ $CRITERIA_COUNT -gt 0 ] && echo 'true' || echo 'false')"

        echo "  Number of criteria: $CRITERIA_COUNT"
        echo ""
        echo "  Criteria results:"
        echo "$RESPONSE" | jq -r '.criteria_results[] | "    [\(.status)] \(.criterion)"'
    else
        echo -e "${YELLOW}SKIP${NC} - No criteria results"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No Evidence Pack"
fi

#############################################
# Test 9: Verify evidence collected
#############################################
echo ""
echo "=== Test 9: Verify Evidence Collected ==="

if [ -n "$EVIDENCE_PACK_ID" ]; then
    RESPONSE=$(curl -s "$BASE_URL/cwom/evidence-packs/$EVIDENCE_PACK_ID")
    EVIDENCE_COUNT=$(echo "$RESPONSE" | jq '.evidence_collected | length')
    EVIDENCE_FOUND=$(echo "$RESPONSE" | jq '[.evidence_collected[] | select(.found == true)] | length')

    if [ "$EVIDENCE_COUNT" -gt 0 ]; then
        run_test "Evidence collected" "true" "$([ $EVIDENCE_COUNT -gt 0 ] && echo 'true' || echo 'false')"

        echo "  Total evidence items: $EVIDENCE_COUNT"
        echo "  Evidence found: $EVIDENCE_FOUND"
        echo ""
        echo "  Evidence items:"
        echo "$RESPONSE" | jq -r '.evidence_collected[] | "    [\(if .found then "✓" else "✗" end)] \(.requirement)"'
    else
        echo -e "${YELLOW}SKIP${NC} - No evidence items"
    fi
else
    echo -e "${YELLOW}SKIP${NC} - No Evidence Pack"
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
