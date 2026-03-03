#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-frontend/apps}"

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required" >&2
  exit 1
fi

pattern='\$\{(?:apiBase|normalizedApiBase)\}/(?!api/v2)'

matches="$(rg -n --pcre2 "$pattern" "$ROOT_DIR" -g '!**/*.test.*' -g '!**/*.spec.*' || true)"

if [[ -n "$matches" ]]; then
  echo "frontend still contains non-v2 api calls:"
  echo "$matches"
  exit 1
fi

echo "frontend api calls are v2-only"
