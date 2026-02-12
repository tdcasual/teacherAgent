#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_PATH = REPO_ROOT / "config" / "backend_quality_budget.json"
APP_CORE_PATH = REPO_ROOT / "services" / "api" / "app_core.py"


@dataclass(frozen=True)
class QualityBudget:
    ruff_max: int
    mypy_max: int
    app_core_max_lines: int


@dataclass(frozen=True)
class QualityMetrics:
    ruff_errors: int
    mypy_errors: int
    app_core_lines: int


def parse_ruff_error_count(output: str) -> int:
    if not output.strip() or "All checks passed!" in output:
        return 0
    match = re.search(r"Found\s+(\d+)\s+errors?\.", output)
    if match:
        return int(match.group(1))
    raise ValueError("unable to parse ruff output")


def parse_mypy_error_count(output: str) -> int:
    if "Success: no issues found" in output:
        return 0
    match = re.search(r"Found\s+(\d+)\s+errors?", output)
    if match:
        return int(match.group(1))
    raise ValueError("unable to parse mypy output")


def load_budget(path: Path = BUDGET_PATH) -> QualityBudget:
    data = json.loads(path.read_text(encoding="utf-8"))
    return QualityBudget(
        ruff_max=int(data["ruff_max"]),
        mypy_max=int(data["mypy_max"]),
        app_core_max_lines=int(data["app_core_max_lines"]),
    )


def run_command(command: Sequence[str]) -> tuple[int, str]:
    completed = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout + completed.stderr


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def collect_metrics() -> tuple[QualityMetrics, dict[str, str]]:
    ruff_rc, ruff_output = run_command([sys.executable, "-m", "ruff", "check", "services/api", "--statistics"])
    if ruff_rc not in (0, 1):
        raise RuntimeError(f"ruff command failed with exit code {ruff_rc}")
    ruff_errors = parse_ruff_error_count(ruff_output)

    mypy_rc, mypy_output = run_command(
        [sys.executable, "-m", "mypy", "--follow-imports=skip", "services/api"]
    )
    if mypy_rc not in (0, 1):
        raise RuntimeError(f"mypy command failed with exit code {mypy_rc}")
    mypy_errors = parse_mypy_error_count(mypy_output)

    metrics = QualityMetrics(
        ruff_errors=ruff_errors,
        mypy_errors=mypy_errors,
        app_core_lines=_line_count(APP_CORE_PATH),
    )
    outputs = {"ruff": ruff_output, "mypy": mypy_output}
    return metrics, outputs


def evaluate_budget(metrics: QualityMetrics, budget: QualityBudget) -> list[str]:
    violations: list[str] = []
    if metrics.ruff_errors > budget.ruff_max:
        violations.append(f"ruff_errors={metrics.ruff_errors} > ruff_max={budget.ruff_max}")
    if metrics.mypy_errors > budget.mypy_max:
        violations.append(f"mypy_errors={metrics.mypy_errors} > mypy_max={budget.mypy_max}")
    if metrics.app_core_lines > budget.app_core_max_lines:
        violations.append(
            f"app_core_lines={metrics.app_core_lines} > app_core_max_lines={budget.app_core_max_lines}"
        )
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check backend quality metrics against configured budget.")
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Collect and print metrics without enforcing budget.",
    )
    parser.add_argument(
        "--show-tool-output",
        action="store_true",
        help="Print raw ruff/mypy output for debugging.",
    )
    args = parser.parse_args(argv)

    budget = load_budget(BUDGET_PATH)
    metrics, outputs = collect_metrics()

    payload = {"budget": asdict(budget), "metrics": asdict(metrics)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.show_tool_output:
        print("\n# ruff output")
        print(outputs["ruff"].rstrip())
        print("\n# mypy output")
        print(outputs["mypy"].rstrip())

    if args.print_only:
        return 0

    violations = evaluate_budget(metrics, budget)
    if violations:
        for violation in violations:
            print(f"[FAIL] {violation}", file=sys.stderr)
        return 1

    print("[OK] Backend quality metrics are within budget.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
