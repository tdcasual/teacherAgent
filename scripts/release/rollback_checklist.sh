#!/usr/bin/env bash
set -euo pipefail

DOC="docs/operations/go-hard-cutover-rollback.md"

[[ -f "$DOC" ]] || { echo "missing rollback runbook: $DOC" >&2; exit 1; }

grep -q "Stop go-api" "$DOC" || { echo "missing step: Stop go-api" >&2; exit 1; }
grep -q "Restore database snapshot" "$DOC" || { echo "missing step: Restore database snapshot" >&2; exit 1; }
grep -q "Re-enable previous stable go-api release" "$DOC" || { echo "missing step: Re-enable previous backend" >&2; exit 1; }
grep -q "Run rollback smoke suite" "$DOC" || { echo "missing step: Run rollback smoke suite" >&2; exit 1; }

echo "rollback checklist OK"
