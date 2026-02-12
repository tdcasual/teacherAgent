#!/usr/bin/env bash
set -euo pipefail

python3 -m ruff check services/api --statistics || true
python3 -m mypy --follow-imports=skip services/api || true
wc -l services/api/app_core.py
