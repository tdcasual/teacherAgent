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

TARGET="${BACKUP_TARGET_DEFAULT:-s3}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/backup/pre_upgrade_snapshot.sh --target s3|oss
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
      echo "unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

bash "${SCRIPT_DIR}/run_backup.sh" --snapshot-type full --target "${TARGET}"

echo "[backup] pre-upgrade snapshot completed on target=${TARGET}"
echo "[backup] next: store output/backups/state/latest_${TARGET}.json in release ticket"
