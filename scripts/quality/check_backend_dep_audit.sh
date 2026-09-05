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
# Starlette 1.x is required to clear current advisories, but FastAPI 0.128.7
# caps starlette at <1. mem0 2.x is still beta; keep 1.0.3 and ignore that ID.
python -m pip_audit -r services/api/requirements.txt \
  --ignore-vuln PYSEC-2026-161 \
  --ignore-vuln PYSEC-2026-248 \
  --ignore-vuln PYSEC-2026-249 \
  --ignore-vuln PYSEC-2026-2280 \
  --ignore-vuln PYSEC-2026-2281 \
  --ignore-vuln PYSEC-2026-2636
