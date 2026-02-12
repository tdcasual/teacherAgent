from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "quality"
        / "check_backend_quality_budget.py"
    )
    spec = importlib.util.spec_from_file_location("quality_budget_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_ruff_error_count() -> None:
    mod = _load_module()
    output = "Found 379 errors.\n[*] 253 fixable with the `--fix` option.\n"
    assert mod.parse_ruff_error_count(output) == 379


def test_parse_ruff_error_count_for_empty_output_when_clean() -> None:
    mod = _load_module()
    assert mod.parse_ruff_error_count("") == 0


def test_parse_mypy_error_count_success_and_failure() -> None:
    mod = _load_module()
    failure = "Found 2 errors in 1 file (checked 216 source files)\n"
    success = "Success: no issues found in 216 source files\n"
    assert mod.parse_mypy_error_count(failure) == 2
    assert mod.parse_mypy_error_count(success) == 0


def test_collect_metrics_reads_budget_path() -> None:
    mod = _load_module()
    assert "backend_quality_budget.json" in str(mod.BUDGET_PATH)
