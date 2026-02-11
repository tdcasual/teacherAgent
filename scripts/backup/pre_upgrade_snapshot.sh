#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

