#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "${REPO_ROOT}"

python -m pip install --upgrade pip pip-audit
python -m pip_audit -r services/api/requirements.txt
