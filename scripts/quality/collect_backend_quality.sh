#!/usr/bin/env bash
set -euo pipefail

# Resolve symlink entrypoints consistently.
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "${SCRIPT_PATH}" ]; do
  LINK_DIR="$(cd -P "$(dirname "${SCRIPT_PATH}")" >/dev/null 2>&1 && pwd)"
  LINK_TARGET="$(readlink "${SCRIPT_PATH}")"
  if [[ "${LINK_TARGET}" = /* ]]; then
    SCRIPT_PATH="${LINK_TARGET}"
  else
    SCRIPT_PATH="${LINK_DIR}/${LINK_TARGET}"
  fi
done
SCRIPT_DIR="$(cd -P "$(dirname "${SCRIPT_PATH}")" >/dev/null 2>&1 && pwd)"

python3 "${SCRIPT_DIR}/check_backend_quality_budget.py" --print-only --show-tool-output

ENABLE_CHAT_STREAM_STABILITY_SMOKE="${ENABLE_CHAT_STREAM_STABILITY_SMOKE:-1}"
if [[ "${ENABLE_CHAT_STREAM_STABILITY_SMOKE}" != "0" ]]; then
  SMOKE_SCRIPT="${SCRIPT_DIR}/../chat_stream_stability_smoke.py"
  if [[ -f "${SMOKE_SCRIPT}" ]]; then
    CHAT_STREAM_SMOKE_JOBS="${CHAT_STREAM_SMOKE_JOBS:-200}"
    CHAT_STREAM_SMOKE_EVENTS_PER_JOB="${CHAT_STREAM_SMOKE_EVENTS_PER_JOB:-6}"
    CHAT_STREAM_SMOKE_WRITERS="${CHAT_STREAM_SMOKE_WRITERS:-16}"
    CHAT_STREAM_SMOKE_SIGNAL_CAP="${CHAT_STREAM_SMOKE_SIGNAL_CAP:-192}"
    CHAT_STREAM_SMOKE_SIGNAL_TTL_SEC="${CHAT_STREAM_SMOKE_SIGNAL_TTL_SEC:-1.2}"
    CHAT_STREAM_SMOKE_REPORT="${CHAT_STREAM_SMOKE_REPORT:-}"

    echo
    echo "# chat stream stability smoke"
    SMOKE_CMD=(
      python3
      "${SMOKE_SCRIPT}"
      --jobs "${CHAT_STREAM_SMOKE_JOBS}"
      --events-per-job "${CHAT_STREAM_SMOKE_EVENTS_PER_JOB}"
      --writers "${CHAT_STREAM_SMOKE_WRITERS}"
      --signal-cap "${CHAT_STREAM_SMOKE_SIGNAL_CAP}"
      --signal-ttl-sec "${CHAT_STREAM_SMOKE_SIGNAL_TTL_SEC}"
    )
    if [[ -n "${CHAT_STREAM_SMOKE_REPORT}" ]]; then
      SMOKE_CMD+=(--report "${CHAT_STREAM_SMOKE_REPORT}")
    fi
    "${SMOKE_CMD[@]}"
  else
    echo "[WARN] chat stream stability smoke script not found at ${SMOKE_SCRIPT}; skipping." >&2
  fi
fi
