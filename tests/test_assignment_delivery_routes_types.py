from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_assignment_delivery_routes_module_mypy_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "services" / "api" / "routes" / "assignment_delivery_routes.py"
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


def test_assignment_delivery_routes_do_not_own_download_acl() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    source = (
        repo_root / "services" / "api" / "routes" / "assignment_delivery_routes.py"
    ).read_text(encoding="utf-8")
    assert "_require_assignment_access" not in source
    assert "forbidden_assignment_scope" not in source
    assert "assignment_specificity" not in source
