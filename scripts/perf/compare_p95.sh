#!/usr/bin/env bash
set -euo pipefail

BASELINE_FILE="${1:-output/rewrite_baseline_p95_ms.txt}"
CURRENT_FILE="${2:-output/rewrite_current_p95_ms.txt}"
THRESHOLD="${P95_IMPROVEMENT_THRESHOLD:-30}"

if [[ ! -f "$BASELINE_FILE" ]]; then
  echo "baseline file not found: $BASELINE_FILE" >&2
  exit 1
fi

if [[ ! -f "$CURRENT_FILE" ]]; then
  echo "current file not found: $CURRENT_FILE" >&2
  exit 1
fi

BASELINE_RAW="$(tr -d '[:space:]' < "$BASELINE_FILE")"
CURRENT_RAW="$(tr -d '[:space:]' < "$CURRENT_FILE")"

if [[ ! "$BASELINE_RAW" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "invalid baseline value: $BASELINE_RAW" >&2
  exit 1
fi

if [[ ! "$CURRENT_RAW" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "invalid current value: $CURRENT_RAW" >&2
  exit 1
fi

if awk "BEGIN{exit !($BASELINE_RAW <= 0)}"; then
  echo "baseline must be > 0, got: $BASELINE_RAW" >&2
  exit 1
fi

IMPROVEMENT="$(awk "BEGIN{printf \"%.2f\", (($BASELINE_RAW - $CURRENT_RAW) / $BASELINE_RAW) * 100}")"

echo "baseline_p95_ms=$BASELINE_RAW"
echo "current_p95_ms=$CURRENT_RAW"
echo "improvement_percent=$IMPROVEMENT"
echo "threshold_percent=$THRESHOLD"

if awk "BEGIN{exit !($IMPROVEMENT >= $THRESHOLD)}"; then
  echo "P95 gate PASS"
  exit 0
fi

echo "P95 gate FAIL: improvement $IMPROVEMENT% is below $THRESHOLD%" >&2
exit 1
