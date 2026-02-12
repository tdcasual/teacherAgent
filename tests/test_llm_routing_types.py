from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_mypy_for(target: Path, repo_root: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=skip",
            str(target),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    assert proc.returncode == 0, output


def test_llm_routing_module_mypy_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "services" / "api" / "llm_routing.py"
    _run_mypy_for(target, repo_root)


def test_llm_routing_resolver_module_mypy_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "services" / "api" / "llm_routing_resolver.py"
    _run_mypy_for(target, repo_root)
