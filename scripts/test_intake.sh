#!/bin/bash
#
# Practical Test Plan: Intake (Step 1)
#
# Tests the full intake flow: Task Spec → Context Packet → Immutable Record
#
# Usage:
#   ./scripts/test_intake.sh [BASE_URL]
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

# Unique suffix to avoid idempotency collisions across runs
RUN_ID=$(date +%s)

echo "=============================================="
echo "  Intake (Step 1) - Practical Test Plan"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Run ID: $RUN_ID"
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

    echo -e "${GREEN}OK${NC}"
}

# Test helper
run_test() {
    local name="$1"
    local expected_status="$2"
    local response="$3"
    local actual_status="$4"
    local validation="$5"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo ""
    echo "--- Test $TESTS_RUN: $name ---"

    if [ "$actual_status" != "$expected_status" ]; then
        echo -e "${RED}FAIL${NC} - Expected HTTP $expected_status, got $actual_status"
        echo "Response: $response"
        FAIL=$((FAIL + 1))
        return 1
    fi

    if [ -n "$validation" ]; then
        if ! eval "$validation"; then
            echo -e "${RED}FAIL${NC} - Validation failed"
            echo "Response: $response"
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
TRACE_ID="test-intake-$RUN_ID"
CONTEXT_PACKET_ID=""

check_prereqs

#############################################
# Test 1: Happy Path - Full Intake Flow
#############################################
echo ""
echo "=== Test 1: Happy Path - Full Intake Flow ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: $TRACE_ID" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"intake-test-$RUN_ID\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"operator\", \"label\": \"Test Operator\"},
    \"objective\": \"Add healthz endpoint that returns JSON status\",
    \"operation\": \"code_change\",
    \"target\": {\"repo\": \"testorg/my-service\", \"ref\": \"main\", \"path\": \"src/api\"},
    \"constraints\": {\"time_budget_seconds\": 600},
    \"acceptance_criteria\": [\"Returns 200 with JSON body\", \"Includes status field\"],
    \"evidence_requirements\": [\"pytest output\", \"curl response screenshot\"]
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

TASK_ID=$(echo "$BODY" | jq -r '.task_id // empty')
CONTEXT_PACKET_ID=$(echo "$BODY" | jq -r '.cwom.context_packet_id // empty')

run_test "Happy Path - Full Intake" "201" "$BODY" "$HTTP_CODE" \
    "[ \"\$(echo '$BODY' | jq -r '.status')\" = 'success' ] && \
     [ \"\$(echo '$BODY' | jq -r '.trace_id')\" = '$TRACE_ID' ] && \
     [ -n '$TASK_ID' ] && \
     [ -n '$CONTEXT_PACKET_ID' ]"

echo "  Task ID: $TASK_ID"
echo "  Context Packet ID: $CONTEXT_PACKET_ID"

#############################################
# Test 2: Idempotency - Duplicate Rejected
#############################################
echo ""
echo "=== Test 2: Idempotency - Duplicate Rejected ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"intake-test-$RUN_ID\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"operator\"},
    \"objective\": \"Different objective this time - should be rejected\",
    \"operation\": \"docs\",
    \"target\": {\"repo\": \"testorg/other-repo\"}
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

RETURNED_TASK_ID=$(echo "$BODY" | jq -r '.task_id // empty')

run_test "Idempotency - Duplicate Rejected" "409" "$BODY" "$HTTP_CODE" \
    "[ \"\$(echo '$BODY' | jq -r '.status')\" = 'conflict' ] && \
     [ '$RETURNED_TASK_ID' = '$TASK_ID' ]"

#############################################
# Test 3: Normalization
#############################################
echo ""
echo "=== Test 3: Normalization ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"intake-normalize-$RUN_ID\",
    \"requested_by\": {\"kind\": \"agent\", \"id\": \"ci-bot\"},
    \"objective\": \"  Whitespace around objective  \",
    \"operation\": \"analysis\",
    \"target\": {\"repo\": \"TestOrg/MyRepo.git\", \"ref\": \"develop\"}
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

NORMALIZED_REPO=$(echo "$BODY" | jq -r '.task.target.repo // empty')
NORMALIZED_OBJECTIVE=$(echo "$BODY" | jq -r '.task.objective // empty')

run_test "Normalization" "201" "$BODY" "$HTTP_CODE" \
    "[ '$NORMALIZED_REPO' = 'testorg/myrepo' ] && \
     [ '$NORMALIZED_OBJECTIVE' = 'Whitespace around objective' ]"

echo "  Normalized repo: $NORMALIZED_REPO"
echo "  Normalized objective: '$NORMALIZED_OBJECTIVE'"

#############################################
# Test 4: Policy Rejection - Disallowed Repo
#############################################
echo ""
echo "=== Test 4: Policy Rejection - Disallowed Repo ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1.0\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"hacker\"},
    \"objective\": \"This should be rejected due to repo policy\",
    \"operation\": \"ops\",
    \"target\": {\"repo\": \"evil-corp/secrets\"}
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

ERROR_CODE=$(echo "$BODY" | jq -r '.detail.code // empty')

run_test "Policy Rejection - Disallowed Repo" "422" "$BODY" "$HTTP_CODE" \
    "[ '$ERROR_CODE' = 'REPO_NOT_ALLOWED' ]"

echo "  Error code: $ERROR_CODE"

#############################################
# Test 5: Policy Rejection - Network Access Denied
#############################################
echo ""
echo "=== Test 5: Policy Rejection - Network Access Denied ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1.0\",
    \"requested_by\": {\"kind\": \"agent\", \"id\": \"bot\"},
    \"objective\": \"Task requesting network access should be denied\",
    \"operation\": \"code_change\",
    \"target\": {\"repo\": \"testorg/valid-repo\"},
    \"constraints\": {\"allow_network\": true}
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

ERROR_CODE=$(echo "$BODY" | jq -r '.detail.code // empty')

run_test "Policy Rejection - Network Access Denied" "422" "$BODY" "$HTTP_CODE" \
    "[ '$ERROR_CODE' = 'NETWORK_ACCESS_DENIED' ]"

echo "  Error code: $ERROR_CODE"

#############################################
# Test 6: CWOM Objects - Verify Context Packet
#############################################
echo ""
echo "=== Test 6: CWOM Objects - Verify Context Packet ==="

if [ -n "$CONTEXT_PACKET_ID" ]; then
    RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/cwom/context-packets/$CONTEXT_PACKET_ID")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    ACCEPTANCE=$(echo "$BODY" | jq -r '.meta.acceptance_criteria[0] // empty')
    EVIDENCE=$(echo "$BODY" | jq -r '.meta.evidence_requirements[0] // empty')

    run_test "CWOM - Context Packet has acceptance_criteria" "200" "$BODY" "$HTTP_CODE" \
        "[ '$ACCEPTANCE' = 'Returns 200 with JSON body' ] && \
         [ '$EVIDENCE' = 'pytest output' ]"

    echo "  acceptance_criteria[0]: $ACCEPTANCE"
    echo "  evidence_requirements[0]: $EVIDENCE"
else
    echo -e "${YELLOW}SKIP${NC} - No context_packet_id from Test 1"
fi

#############################################
# Test 7: Retrieve Task by ID
#############################################
echo ""
echo "=== Test 7: Retrieve Task by ID ==="

if [ -n "$TASK_ID" ]; then
    RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/tasks/$TASK_ID")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    TASK_STATUS=$(echo "$BODY" | jq -r '.status // empty')

    run_test "Retrieve Task by ID" "200" "$BODY" "$HTTP_CODE" \
        "[ '$TASK_STATUS' = 'queued' ]"

    echo "  Task status: $TASK_STATUS"
else
    echo -e "${YELLOW}SKIP${NC} - No task_id from Test 1"
fi

#############################################
# Test 8: Legacy Schema Support
#############################################
echo ""
echo "=== Test 8: Legacy Schema Support ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"intake-legacy-$RUN_ID\",
    \"requested_by\": {\"kind\": \"system\", \"id\": \"legacy-client\"},
    \"objective\": \"Test legacy field aliases\",
    \"type\": \"docs\",
    \"target\": {\"repository\": \"testorg/legacy-repo\"},
    \"payload\": {\"format\": \"markdown\"}
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

OPERATION=$(echo "$BODY" | jq -r '.task.operation // empty')
REPO=$(echo "$BODY" | jq -r '.task.target.repo // empty')
INPUTS=$(echo "$BODY" | jq -r '.task.inputs.format // empty')

run_test "Legacy Schema Support" "201" "$BODY" "$HTTP_CODE" \
    "[ '$OPERATION' = 'docs' ] && \
     [ '$REPO' = 'testorg/legacy-repo' ] && \
     [ '$INPUTS' = 'markdown' ]"

echo "  type → operation: $OPERATION"
echo "  repository → repo: $REPO"
echo "  payload → inputs.format: $INPUTS"

#############################################
# Test 9: No CWOM when create_cwom=false
#############################################
echo ""
echo "=== Test 9: No CWOM when create_cwom=false ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue?create_cwom=false" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"intake-no-cwom-$RUN_ID\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"tester\"},
    \"objective\": \"Task without CWOM objects\",
    \"operation\": \"analysis\",
    \"target\": {\"repo\": \"testorg/no-cwom-repo\"}
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

HAS_CWOM=$(echo "$BODY" | jq 'has("cwom")')

run_test "No CWOM when create_cwom=false" "201" "$BODY" "$HTTP_CODE" \
    "[ '$HAS_CWOM' = 'false' ]"

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
