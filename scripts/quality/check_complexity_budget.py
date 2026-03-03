#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_PATH = REPO_ROOT / "config" / "function_complexity_budget.json"


def _load_budget() -> Dict[str, Any]:
    payload = json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("function complexity budget must be a JSON object")
    return payload


def _run_ruff_c901(max_complexity: int) -> List[Dict[str, Any]]:
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "services/api",
        "--select",
        "C901",
        "--config",
        f"lint.mccabe.max-complexity={int(max_complexity)}",
        "--output-format",
        "json",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = (result.stdout or "").strip()
    if not stdout:
        return []
    data = json.loads(stdout)
    return data if isinstance(data, list) else []


def _summarize(issues: List[Dict[str, Any]]) -> Tuple[int, Dict[str, int]]:
    per_file: Dict[str, int] = {}
    for item in issues:
        raw_file = str(item.get("filename") or "").replace("\\", "/")
        if not raw_file:
            continue
        rel_file = str(Path(raw_file))
        if not rel_file.startswith("services/api/"):
            try:
                rel_file = Path(raw_file).relative_to(REPO_ROOT).as_posix()
            except Exception:
                rel_file = raw_file
        per_file[rel_file] = int(per_file.get(rel_file, 0)) + 1
    return len(issues), per_file


def main() -> int:
    budget = _load_budget()
    max_complexity = max(1, int(budget.get("mccabe_max_complexity") or 10))
    total_max = int(budget.get("total_c901_max") or 0)
    critical_budget = budget.get("critical_files") or {}
    if not isinstance(critical_budget, dict):
        raise ValueError("critical_files must be a JSON object")

    issues = _run_ruff_c901(max_complexity)
    total, per_file = _summarize(issues)
    violations: List[str] = []

    if total > total_max:
        violations.append(f"total C901={total} exceeds budget={total_max}")

    for path, file_max_raw in critical_budget.items():
        file_max = int(file_max_raw or 0)
        count = int(per_file.get(str(path), 0))
        if count > file_max:
            violations.append(f"{path}: C901={count} exceeds budget={file_max}")

    if violations:
        print("[FAIL] Complexity budget violations:")
        for item in violations:
            print(f"- {item}")
        print("[INFO] Current C901 by critical files:")
        for path in sorted(critical_budget.keys()):
            print(f"- {path}: {int(per_file.get(str(path), 0))}")
        print(f"[INFO] Current total C901: {total} (max complexity>{max_complexity})")
        return 1

    print("[OK] Complexity budget check passed.")
    print(f"[INFO] Current total C901: {total} / budget {total_max} (max complexity>{max_complexity})")
    for path in sorted(critical_budget.keys()):
        print(
            f"[INFO] {path}: {int(per_file.get(str(path), 0))} / budget {int(critical_budget[path])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
