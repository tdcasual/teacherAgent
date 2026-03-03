#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

ALLOW_MARKER = "policy: allowed-broad-except"
TARGET_FILES: Sequence[str] = (
    "services/api/chart_executor.py",
    "services/api/chat_job_processing_service.py",
    "services/api/auth_registry_service.py",
    "services/api/teacher_memory_core.py",
)

_BROAD_EXCEPT_RE = re.compile(
    r"^\s*except\s+(?:Exception(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?|)\s*:\s*(?:#.*)?$"
)
_PASS_RE = re.compile(r"^\s*pass\s*(?:#.*)?$")


def _has_allow_marker(line: str) -> bool:
    return ALLOW_MARKER in line


def _iter_policy_violations(path: Path) -> Iterable[Tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for index, raw in enumerate(lines):
        line_no = index + 1
        line = raw.rstrip("\n")
        prev = lines[index - 1] if index > 0 else ""
        marker_ok = _has_allow_marker(line) or _has_allow_marker(prev)

        if _BROAD_EXCEPT_RE.match(line):
            if not marker_ok:
                yield line_no, "broad-except without policy marker"
            continue

        if _PASS_RE.match(line):
            if not marker_ok:
                yield line_no, "empty-pass without policy marker"


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: Sequence[str]) -> int:
    repo_root = _resolve_repo_root()
    targets = [repo_root / rel for rel in TARGET_FILES]
    violations: List[str] = []

    for path in targets:
        if not path.exists():
            violations.append(f"{path}: missing target file")
            continue
        for line_no, detail in _iter_policy_violations(path):
            rel = path.relative_to(repo_root).as_posix()
            violations.append(f"{rel}:{line_no}: {detail}")

    if violations:
        print("[FAIL] Exception policy violations:")
        for item in violations:
            print(f"- {item}")
        return 1

    if "--quiet" not in argv:
        print(f"[OK] Exception policy passed for {len(targets)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
