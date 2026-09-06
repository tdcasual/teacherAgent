from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_APPLICATION_MODULES = [
    "services/api/assignment/application.py",
    "services/api/student_submit_service.py",
]


def test_assignment_application_module_mypy_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "services" / "api" / "assignment" / "application.py"
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


def test_application_modules_do_not_import_fastapi() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for relative in _APPLICATION_MODULES:
        source = (repo_root / relative).read_text(encoding="utf-8")
        assert "from fastapi" not in source, f"{relative} still imports fastapi"
        assert "import fastapi" not in source, f"{relative} still imports fastapi"
