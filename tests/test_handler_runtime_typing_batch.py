from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_MODULES = [
    "services/api/handlers/assignment_handlers.py",
    "services/api/handlers/assignment_upload_handlers.py",
    "services/api/handlers/assignment_io_handlers.py",
    "services/api/handlers/chat_handlers.py",
    "services/api/runtime/bootstrap.py",
    "services/api/workers/inline_runtime.py",
    "services/api/tenant_admin_api.py",
    "services/api/chat_job_service.py",
    "services/api/app.py",
]


@pytest.mark.parametrize("relative_path", _MODULES)
def test_handler_runtime_module_mypy_clean(relative_path: str) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / relative_path
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
