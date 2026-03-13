#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Tuple

ALLOW_MARKER = "policy: allowed-broad-except"
ALLOWLIST_REL_PATH = "config/exception_policy_allowlist.txt"

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


def _iter_targets(repo_root: Path) -> List[Path]:
    root = repo_root / "services" / "api"
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _load_allowlist(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    items: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        items.add(line)
    return items


def _collapse_violation(violation: str) -> str:
    path, _line_no, detail = violation.split(":", 2)
    return f"{path}:*: {detail.strip()}"


def _allowlist_matches(violation: str, pattern: str) -> bool:
    if violation == pattern:
        return True
    return fnmatch.fnmatchcase(violation, pattern)


def _write_allowlist(path: Path, violations: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    patterns = sorted({_collapse_violation(violation) for violation in violations})
    body = [
        "# Exception policy allowlist",
        "# Format: relative/path.py:*: detail (or an exact relative/path.py:line: detail entry)",
        *patterns,
    ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def main(argv: Sequence[str]) -> int:
    repo_root = _resolve_repo_root()
    allowlist_path = repo_root / ALLOWLIST_REL_PATH
    sync_allowlist = "--sync-allowlist" in argv
    quiet = "--quiet" in argv
    current_violations: List[str] = []

    for path in _iter_targets(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        for line_no, detail in _iter_policy_violations(path):
            current_violations.append(f"{rel}:{line_no}: {detail}")

    if sync_allowlist:
        _write_allowlist(allowlist_path, current_violations)
        if not quiet:
            print(f"[OK] Synced allowlist with {len(current_violations)} entries: {ALLOWLIST_REL_PATH}")
        return 0

    allowlist = sorted(_load_allowlist(allowlist_path))
    new_violations = sorted(
        violation
        for violation in current_violations
        if not any(_allowlist_matches(violation, pattern) for pattern in allowlist)
    )
    stale_allowlist = sorted(
        pattern
        for pattern in allowlist
        if not any(_allowlist_matches(violation, pattern) for violation in current_violations)
    )

    if new_violations:
        print("[FAIL] Exception policy violations not in allowlist:")
        for item in new_violations:
            print(f"- {item}")
        print(
            f"[HINT] Run: {sys.executable} {Path(__file__).as_posix()} --sync-allowlist "
            "after intentional debt updates."
        )
        return 1

    if not quiet:
        print(f"[OK] Exception policy check passed for services/api (tracked violations={len(current_violations)}).")
        print(f"[INFO] allowlist: {ALLOWLIST_REL_PATH}")
        if stale_allowlist:
            print(f"[WARN] Allowlist contains {len(stale_allowlist)} stale entries (cleanup recommended).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
