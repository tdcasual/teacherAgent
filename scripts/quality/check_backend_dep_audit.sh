#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "${REPO_ROOT}"

REQS="services/api/requirements.txt"
for pkg in deepseek-ocr multi-ocr-sdk; do
  if grep -E "^${pkg}[[:space:]]*>=" "${REQS}" >/dev/null; then
    echo "error: ${pkg} must not use >= in ${REQS}; pin with ==" >&2
    exit 1
  fi
  if ! grep -E "^${pkg}==" "${REQS}" >/dev/null; then
    echo "error: ${pkg} must be pinned with == in ${REQS}" >&2
    exit 1
  fi
done

python -m pip install --upgrade pip pip-audit
python -m pip_audit -r services/api/requirements.txt
