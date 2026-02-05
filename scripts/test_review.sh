#!/bin/bash
#
# Practical Test Plan: Review (Step 5)
#
# Tests the review flow: EvidencePack -> ReviewDecision -> Status transitions
#
# Usage:
#   ./scripts/test_review.sh [BASE_URL]
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
NC='\033[0m'

# Unique suffix for this test run
SUFFIX=$(date +%s)

echo "=============================================="
echo "  Review (Step 5) - Practical Test Plan"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Suffix: $SUFFIX"
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

    echo -e "${GREEN}OK${NC}"
}

# Test helper
run_test() {
    local name="$1"
    local expected="$2"
    local actual="$3"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo ""
    echo "--- Test $TESTS_RUN: $name ---"

    if [ "$actual" != "$expected" ]; then
        echo -e "${RED}FAIL${NC} - Expected '$expected', got '$actual'"
        FAIL=$((FAIL + 1))
        return 1
    fi

    echo -e "${GREEN}PASS${NC}"
    PASS=$((PASS + 1))
    return 0
}

check_prereqs

#############################################
# Setup: Create Repo + Issue + Run + EvidencePack
#############################################
echo ""
echo "=== Setup: Creating CWOM objects ==="

# Create repo
REPO_RESP=$(curl -s -X POST "$BASE_URL/cwom/repos" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Review Test $SUFFIX\",
    \"slug\": \"testorg/review-$SUFFIX\",
    \"source\": {\"system\": \"github\"}
  }")
REPO_ID=$(echo "$REPO_RESP" | jq -r '.repo.id')
echo "  Repo ID: $REPO_ID"

# Create issue
ISSUE_RESP=$(curl -s -X POST "$BASE_URL/cwom/issues" \
  -H "Content-Type: application/json" \
  -d "{
    \"repo\": {\"kind\": \"Repo\", \"id\": \"$REPO_ID\"},
    \"title\": \"Review test issue $SUFFIX\",
    \"type\": \"feature\"
  }")
ISSUE_ID=$(echo "$ISSUE_RESP" | jq -r '.issue.id')
echo "  Issue ID: $ISSUE_ID"

# Create run
RUN_RESP=$(curl -s -X POST "$BASE_URL/cwom/runs" \
  -H "Content-Type: application/json" \
  -d "{
    \"for_issue\": {\"kind\": \"Issue\", \"id\": \"$ISSUE_ID\"},
    \"repo\": {\"kind\": \"Repo\", \"id\": \"$REPO_ID\"},
    \"mode\": \"agent\",
    \"executor\": {
      \"actor\": {\"actor_kind\": \"system\", \"actor_id\": \"worker-1\"},
      \"runtime\": \"local\"
    }
  }")
RUN_ID=$(echo "$RUN_RESP" | jq -r '.run.id')
echo "  Run ID: $RUN_ID"

# Update run to done (simulating work completion)
curl -s -X PATCH "$BASE_URL/cwom/runs/$RUN_ID" \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}' > /dev/null

# Update issue to under_review (simulating worker setting review status)
curl -s -X PATCH "$BASE_URL/cwom/issues/$ISSUE_ID/status?status=under_review" > /dev/null

echo "  Issue status: under_review"
echo "  Run status: done"
echo ""

#############################################
# Test 1: Verify issue is under_review
#############################################
ISSUE_CHECK=$(curl -s "$BASE_URL/cwom/issues/$ISSUE_ID")
ISSUE_STATUS=$(echo "$ISSUE_CHECK" | jq -r '.status')
run_test "Issue is under_review" "under_review" "$ISSUE_STATUS"

#############################################
# Test 2: Submit review (approved)
#############################################
echo ""
echo "=== Test 2: Submit Review (approved) ==="

# We need an evidence pack first - create one via task enqueue + worker,
# or directly if there's an API. Since there's no POST /cwom/evidence-packs,
# we'll test the review endpoints that don't require one first,
# then use a full task flow.

# Actually, let's create a task and run the worker for a full e2e test
TASK_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/tasks/enqueue?create_cwom=true" \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: review-test-$SUFFIX" \
  -d "{
    \"version\": \"1.0\",
    \"idempotency_key\": \"review-test-$SUFFIX\",
    \"requested_by\": {\"kind\": \"human\", \"id\": \"tester\"},
    \"objective\": \"Test review flow\",
    \"operation\": \"code_change\",
    \"target\": {\"repo\": \"testorg/review-e2e-$SUFFIX\", \"ref\": \"main\"},
    \"constraints\": {\"time_budget_seconds\": 60},
    \"acceptance_criteria\": [\"Task completes\"],
    \"evidence_requirements\": [\"Stub Output\"]
  }")

HTTP_CODE=$(echo "$TASK_RESP" | tail -n1)
BODY=$(echo "$TASK_RESP" | sed '$d')
TASK_ID=$(echo "$BODY" | jq -r '.task_id // empty')
TASK_ISSUE_ID=$(echo "$BODY" | jq -r '.cwom.issue_id // empty')

run_test "Task created for e2e" "201" "$HTTP_CODE"
echo "  Task ID: $TASK_ID"
echo "  Issue ID: $TASK_ISSUE_ID"

#############################################
# Test 3: Run worker to process task
#############################################
echo ""
echo "=== Test 3: Run Worker ==="

export JCT_TRACE_ROOT="${JCT_TRACE_ROOT:-file:///tmp/jct-review-test}"
mkdir -p "${JCT_TRACE_ROOT#file://}"

echo "Starting worker..."
timeout 15s python3 -m devops_control_tower.worker --poll-interval 1 &
WORKER_PID=$!

sleep 8

kill $WORKER_PID 2>/dev/null || true
wait $WORKER_PID 2>/dev/null || true

echo "Worker stopped."

# Check task status
TASK_CHECK=$(curl -s "$BASE_URL/tasks/$TASK_ID")
TASK_STATUS=$(echo "$TASK_CHECK" | jq -r '.status')

run_test "Task completed" "completed" "$TASK_STATUS"

#############################################
# Test 4: Check issue status after worker
#############################################
echo ""
echo "=== Test 4: Issue Status After Worker ==="

ISSUE2_CHECK=$(curl -s "$BASE_URL/cwom/issues/$TASK_ISSUE_ID")
ISSUE2_STATUS=$(echo "$ISSUE2_CHECK" | jq -r '.status')

# Should be under_review (manual review) or done (auto-approve)
# Default config has auto-approve OFF, so expect under_review
run_test "Issue under_review or done" "true" "$([ "$ISSUE2_STATUS" = "under_review" ] || [ "$ISSUE2_STATUS" = "done" ] && echo 'true' || echo 'false')"
echo "  Issue status: $ISSUE2_STATUS"

#############################################
# Test 5: Get evidence pack for the run
#############################################
echo ""
echo "=== Test 5: Get Evidence Pack ==="

# Find the run for the task issue
RUNS_RESP=$(curl -s "$BASE_URL/cwom/runs?issue_id=$TASK_ISSUE_ID")
E2E_RUN_ID=$(echo "$RUNS_RESP" | jq -r '.[0].id // empty')

if [ -n "$E2E_RUN_ID" ]; then
    EP_RESP=$(curl -s "$BASE_URL/cwom/runs/$E2E_RUN_ID/evidence-pack")
    EP_ID=$(echo "$EP_RESP" | jq -r '.id // empty')
    EP_VERDICT=$(echo "$EP_RESP" | jq -r '.verdict // empty')

    run_test "Evidence pack exists" "true" "$([ -n '$EP_ID' ] && echo 'true' || echo 'false')"
    echo "  Evidence Pack ID: $EP_ID"
    echo "  Verdict: $EP_VERDICT"
else
    echo -e "${YELLOW}SKIP${NC} - No run found"
    TESTS_RUN=$((TESTS_RUN + 1))
    FAIL=$((FAIL + 1))
fi

#############################################
# Test 6: Submit manual review if under_review
#############################################
echo ""
echo "=== Test 6: Submit Manual Review ==="

if [ "$ISSUE2_STATUS" = "under_review" ] && [ -n "$EP_ID" ]; then
    REVIEW_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/cwom/reviews" \
      -H "Content-Type: application/json" \
      -d "{
        \"for_evidence_pack\": {\"kind\": \"EvidencePack\", \"id\": \"$EP_ID\"},
        \"for_run\": {\"kind\": \"Run\", \"id\": \"$E2E_RUN_ID\"},
        \"for_issue\": {\"kind\": \"Issue\", \"id\": \"$TASK_ISSUE_ID\"},
        \"reviewer\": {
          \"actor_kind\": \"human\",
          \"actor_id\": \"tester\",
          \"display\": \"Test Reviewer\"
        },
        \"decision\": \"approved\",
        \"decision_reason\": \"LGTM - all checks passed in e2e test\"
      }")

    REVIEW_HTTP=$(echo "$REVIEW_RESP" | tail -n1)
    REVIEW_BODY=$(echo "$REVIEW_RESP" | sed '$d')
    REVIEW_ID=$(echo "$REVIEW_BODY" | jq -r '.review.id // empty')
    REVIEW_DECISION=$(echo "$REVIEW_BODY" | jq -r '.review.decision // empty')

    run_test "Review created" "201" "$REVIEW_HTTP"
    echo "  Review ID: $REVIEW_ID"
    echo "  Decision: $REVIEW_DECISION"
else
    echo -e "${YELLOW}SKIP${NC} - Issue not under_review or no evidence pack"
    REVIEW_ID=""
fi

#############################################
# Test 7: Verify issue transitioned to done
#############################################
echo ""
echo "=== Test 7: Issue Done After Approval ==="

FINAL_ISSUE=$(curl -s "$BASE_URL/cwom/issues/$TASK_ISSUE_ID")
FINAL_STATUS=$(echo "$FINAL_ISSUE" | jq -r '.status')

run_test "Issue done after approval" "done" "$FINAL_STATUS"

#############################################
# Test 8: Get review by ID
#############################################
echo ""
echo "=== Test 8: Get Review by ID ==="

if [ -n "$REVIEW_ID" ]; then
    REVIEW_GET=$(curl -s "$BASE_URL/cwom/reviews/$REVIEW_ID")
    REVIEW_GET_DECISION=$(echo "$REVIEW_GET" | jq -r '.decision // empty')

    run_test "Get review by ID" "approved" "$REVIEW_GET_DECISION"
else
    echo -e "${YELLOW}SKIP${NC} - No review ID"
fi

#############################################
# Test 9: List reviews for issue
#############################################
echo ""
echo "=== Test 9: List Reviews for Issue ==="

REVIEWS_LIST=$(curl -s "$BASE_URL/cwom/issues/$TASK_ISSUE_ID/reviews")
REVIEW_COUNT=$(echo "$REVIEWS_LIST" | jq '. | length')

run_test "Reviews for issue" "true" "$([ $REVIEW_COUNT -ge 1 ] && echo 'true' || echo 'false')"
echo "  Reviews found: $REVIEW_COUNT"

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
