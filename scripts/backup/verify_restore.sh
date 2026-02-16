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
# shellcheck source=scripts/backup/common.sh
source "${SCRIPT_DIR}/common.sh"

TARGET="${BACKUP_TARGET_DEFAULT:-s3}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/backup/verify_restore.sh --target s3|oss
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown arg: $1"
      ;;
  esac
done

TARGET="$(normalize_target "${TARGET}")"
ensure_provider_env "${TARGET}"

STATE_JSON="$(load_latest_state "${TARGET}")"

ARCHIVE_KEY="$(python3 - <<PY
import json
data = json.loads(${STATE_JSON@Q}) if ${STATE_JSON@Q}.strip() else {}
print(((data.get('archive') or {}).get('object_key') or '').strip())
PY
)"

ARCHIVE_SHA="$(python3 - <<PY
import json
data = json.loads(${STATE_JSON@Q}) if ${STATE_JSON@Q}.strip() else {}
print(((data.get('archive') or {}).get('sha256') or '').strip())
PY
)"

[[ -n "${ARCHIVE_KEY}" ]] || die "no latest backup state found for target=${TARGET}"
[[ -n "${ARCHIVE_SHA}" ]] || die "latest backup missing sha256"

VERIFY_ID="rv_${TARGET}_$(now_compact)"
VERIFY_DIR="${PROJECT_ROOT}/output/backups/restore-verify/${VERIFY_ID}"
mkdir -p "${VERIFY_DIR}"

DOWNLOADED_ARCHIVE="${VERIFY_DIR}/payload.tar.gz"
download_object "${TARGET}" "${ARCHIVE_KEY}" "${DOWNLOADED_ARCHIVE}"

DOWNLOADED_SHA="$(sha256_file "${DOWNLOADED_ARCHIVE}")"
[[ "${DOWNLOADED_SHA}" == "${ARCHIVE_SHA}" ]] || die "sha mismatch: expected=${ARCHIVE_SHA} actual=${DOWNLOADED_SHA}"

EXTRACT_DIR="${VERIFY_DIR}/extract"
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${DOWNLOADED_ARCHIVE}" -C "${EXTRACT_DIR}"

python3 - <<PY >"${VERIFY_DIR}/verify_report.json"
import json
from datetime import datetime, timezone
from pathlib import Path

extract = Path(${EXTRACT_DIR@Q})
files = [str(p.relative_to(extract)) for p in extract.rglob('*') if p.is_file()]
report = {
    "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "target": ${TARGET@Q},
    "archive_key": ${ARCHIVE_KEY@Q},
    "file_count": len(files),
    "sample_files": files[:30],
    "ok": True,
}
print(json.dumps(report, ensure_ascii=False, indent=2))
PY

log "restore verify success: target=${TARGET} archive=${ARCHIVE_KEY}"
log "report=${VERIFY_DIR}/verify_report.json"
