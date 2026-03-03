#!/usr/bin/env bash
set -euo pipefail

DOC="docs/operations/go-hard-cutover-runbook.md"
GO_COMPOSE="docker-compose.go-exclusive.yml"
GO_SMOKE="scripts/release/smoke_go_api_v2.sh"

[[ -f "$DOC" ]] || { echo "missing runbook: $DOC" >&2; exit 1; }
[[ -f "$GO_COMPOSE" ]] || { echo "missing go-exclusive compose: $GO_COMPOSE" >&2; exit 1; }
[[ -f "$GO_SMOKE" ]] || { echo "missing go-api smoke script: $GO_SMOKE" >&2; exit 1; }

grep -q "Stop old backend" "$DOC" || { echo "missing step: Stop old backend" >&2; exit 1; }
grep -q "Backup old database" "$DOC" || { echo "missing step: Backup old database" >&2; exit 1; }
grep -q "Deploy go-api" "$DOC" || { echo "missing step: Deploy go-api" >&2; exit 1; }
grep -q "Run v2 smoke suite" "$DOC" || { echo "missing step: Run v2 smoke suite" >&2; exit 1; }
grep -q "docker-compose.go-exclusive.yml" "$DOC" || { echo "missing go compose command in runbook" >&2; exit 1; }

echo "cutover checklist OK"
