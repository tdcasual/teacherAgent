#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"

tmp_body="$(mktemp)"
trap 'rm -f "$tmp_body"' EXIT

PASS_COUNT=0

compact_body() {
  tr -d '\r\n\t ' <"$tmp_body"
}

run_case() {
  local id="$1"
  local method="$2"
  local path="$3"
  local payload="${4:-}"
  local expect_code="$5"
  local expect_contains="$6"

  local code
  if [[ -n "$payload" ]]; then
    code="$(curl -sS -o "$tmp_body" -w "%{http_code}" \
      -X "$method" \
      -H "Content-Type: application/json" \
      --data "$payload" \
      "${API_BASE}${path}")"
  else
    code="$(curl -sS -o "$tmp_body" -w "%{http_code}" \
      -X "$method" \
      "${API_BASE}${path}")"
  fi

  if [[ "$code" != "$expect_code" ]]; then
    echo "[$id] FAIL: expected status $expect_code got $code"
    cat "$tmp_body"
    exit 1
  fi

  local compact
  compact="$(compact_body)"
  local needle
  needle="$(echo "$expect_contains" | tr -d '\r\n\t ')"
  if [[ "$compact" != *"$needle"* ]]; then
    echo "[$id] FAIL: response does not contain expected fragment: $expect_contains"
    cat "$tmp_body"
    exit 1
  fi

  PASS_COUNT=$((PASS_COUNT + 1))
  echo "[$id] PASS"
}

run_case "S01" "GET" "/healthz" "" "200" '"status":"ok"'
run_case "S02" "GET" "/health" "" "200" '"status":"ok"'

run_case "S03" "POST" "/api/v2/auth/student/login" '{"student_id":"stu-1","credential":"S-123"}' "200" '"access_token":"token-stu-1"'
run_case "S04" "POST" "/api/v2/auth/student/login" '{"student_id":"stu-1","credential":"wrong"}' "401" '"error_code":"AUTH_INVALID_CREDENTIAL"'

run_case "S05" "POST" "/api/v2/files/upload" '{"file_name":"lesson.pdf","size_bytes":1024}' "200" '"resource_id":"local-lesson.pdf"'
run_case "S06" "POST" "/api/v2/files/upload" '{"file_name":"big.pdf","size_bytes":73400320}' "413" '"error_code":"FILE_TOO_LARGE"'

run_case "S07" "POST" "/api/v2/assignment/confirm" '{"draft_id":"d1"}' "200" '"status":"queued"'
run_case "S08" "POST" "/api/v2/assignment/confirm" '{"draft_id":"invalid-state"}' "409" '"error_code":"ASSIGNMENT_INVALID_STATE"'

run_case "S09" "POST" "/api/v2/exam/parse" '{"resource_id":"res-1"}' "200" '"status":"queued"'
run_case "S10" "POST" "/api/v2/exam/parse" '{"resource_id":""}' "400" '"error_code":"EXAM_RESOURCE_REQUIRED"'

run_case "S11" "POST" "/api/v2/chat/send" '{"session_id":"s1","message":"hello"}' "200" '"job_id":"chat-job-1"'
run_case "S12" "POST" "/api/v2/chat/send" '{"session_id":"s1","message":""}' "400" '"error_code":"CHAT_MESSAGE_REQUIRED"'

run_case "S13" "GET" "/api/v2/chat/events?job_id=chat-job-1" "" "200" 'event:done'
run_case "S14" "GET" "/api/v2/jobs/chat-job-1" "" "200" '"state":"done"'

run_case "S15" "POST" "/api/v2/admin/teacher/reset-token" '{"teacher_id":"t1"}' "200" '"token":"T-NEW-1"'
run_case "S16" "POST" "/api/v2/admin/teacher/reset-token" '{"teacher_id":""}' "400" '"error_code":"ADMIN_TEACHER_REQUIRED"'
run_case "S17" "POST" "/api/v2/admin/teacher/reset-token" '{"teacher_id":"fail"}' "500" '"error_code":"ADMIN_RESET_TOKEN_FAILED"'
run_case "S18" "GET" "/charts/missing/nope.png" "" "404" '"error_code":"CHART_NOT_FOUND"'
run_case "S19" "GET" "/chart-runs/missing/meta" "" "404" '"error_code":"CHART_RUN_NOT_FOUND"'
run_case "S20" "GET" "/charts/missing/nope.svg" "" "404" '"error_code":"CHART_NOT_FOUND"'

echo "go-api v2 smoke PASS (${PASS_COUNT} cases)"
