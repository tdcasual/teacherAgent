#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/backup/common.sh
source "${SCRIPT_DIR}/common.sh"

SNAPSHOT_TYPE="incremental"
TARGET="${BACKUP_TARGET_DEFAULT:-s3}"
DRY_RUN="0"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/backup/run_backup.sh --snapshot-type incremental|full --target s3|oss [--dry-run]

Examples:
  bash scripts/backup/run_backup.sh --snapshot-type incremental --target s3
  bash scripts/backup/run_backup.sh --snapshot-type full --target oss --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot-type)
      SNAPSHOT_TYPE="${2:-}"
      shift 2
      ;;
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
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
[[ "${SNAPSHOT_TYPE}" == "incremental" || "${SNAPSHOT_TYPE}" == "full" ]] || die "invalid --snapshot-type"
ensure_provider_env "${TARGET}"

JOB_TS="$(now_compact)"
JOB_ID="bk_${SNAPSHOT_TYPE}_${TARGET}_${JOB_TS}"
JOB_DIR="${BACKUP_WORK_DIR}/${JOB_ID}"
mkdir -p "${JOB_DIR}"

INCLUDE_LIST="${JOB_DIR}/include.list"
DOMAINS_JSON="${JOB_DIR}/domains.json"
ARCHIVE_PATH="${JOB_DIR}/payload.tar.gz"
MANIFEST_PATH="${JOB_DIR}/backup_manifest.json"

collect_domain_paths "${DOMAINS_JSON}"

python3 - <<PY >"${INCLUDE_LIST}"
import json
from pathlib import Path

project = Path(${PROJECT_ROOT@Q})
domains = json.loads(Path(${DOMAINS_JSON@Q}).read_text(encoding="utf-8"))
items = []
for item in domains:
    rel = str(item.get("path") or "").strip()
    if not rel:
        continue
    path = project / rel
    if path.exists():
        items.append(rel)

for rel in sorted(set(items)):
    print(rel)
PY

if [[ ! -s "${INCLUDE_LIST}" ]]; then
  die "include list is empty; no paths collected"
fi

build_archive "${ARCHIVE_PATH}" "${INCLUDE_LIST}" "${SNAPSHOT_TYPE}"
ARCHIVE_SHA="$(sha256_file "${ARCHIVE_PATH}")"
ARCHIVE_SIZE="$(wc -c <"${ARCHIVE_PATH}" | tr -d ' ')"

OBJECT_PREFIX="backups/${BACKUP_NAMESPACE}/${TARGET}/${SNAPSHOT_TYPE}/$(date -u +%Y/%m/%d)"
ARCHIVE_KEY="${OBJECT_PREFIX}/${JOB_ID}.tar.gz"
MANIFEST_KEY="${OBJECT_PREFIX}/${JOB_ID}.manifest.json"

python3 - <<PY >"${MANIFEST_PATH}"
import json
from datetime import datetime, timezone
from pathlib import Path

manifest = {
    "job_id": ${JOB_ID@Q},
    "namespace": ${BACKUP_NAMESPACE@Q},
    "target_provider": ${TARGET@Q},
    "snapshot_type": ${SNAPSHOT_TYPE@Q},
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "archive": {
        "object_key": ${ARCHIVE_KEY@Q},
        "sha256": ${ARCHIVE_SHA@Q},
        "size_bytes": int(${ARCHIVE_SIZE@Q}),
    },
    "manifest": {
        "object_key": ${MANIFEST_KEY@Q},
    },
    "retention": {
        "hot_days": int(${BACKUP_HOT_DAYS:-30}),
        "cold_days": int(${BACKUP_COLD_DAYS:-180}),
    },
    "schema_versions": {
        "exam_manifest": 1,
        "assignment_meta": 1,
        "student_profile": 1,
    },
    "source_paths": [
        p.strip() for p in Path(${INCLUDE_LIST@Q}).read_text(encoding="utf-8").splitlines() if p.strip()
    ],
}
print(json.dumps(manifest, ensure_ascii=False, indent=2))
PY

if [[ "${DRY_RUN}" == "1" ]]; then
  log "dry-run done: ${JOB_ID}"
  cat "${MANIFEST_PATH}"
  exit 0
fi

upload_object "${TARGET}" "${ARCHIVE_PATH}" "${ARCHIVE_KEY}"
upload_object "${TARGET}" "${MANIFEST_PATH}" "${MANIFEST_KEY}"

LATEST_STATE="$(cat "${MANIFEST_PATH}")"
write_latest_state "${TARGET}" "${LATEST_STATE}"

log "backup success: job_id=${JOB_ID} target=${TARGET} snapshot=${SNAPSHOT_TYPE}"
log "archive=${ARCHIVE_KEY}"
log "manifest=${MANIFEST_KEY}"

