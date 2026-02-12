from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROUTE_MODULES = [
    "services/api/routes/student_ops_routes.py",
    "services/api/routes/skill_import_routes.py",
    "services/api/routes/skill_crud_routes.py",
    "services/api/routes/exam_upload_routes.py",
    "services/api/routes/exam_query_routes.py",
    "services/api/routes/assignment_upload_routes.py",
    "services/api/routes/assignment_listing_routes.py",
    "services/api/routes/chat_routes.py",
    "services/api/routes/teacher_llm_routing_routes.py",
    "services/api/routes/teacher_provider_registry_routes.py",
    "services/api/routes/teacher_history_routes.py",
    "services/api/routes/teacher_memory_routes.py",
]


@pytest.mark.parametrize("relative_path", _ROUTE_MODULES)
def test_route_module_mypy_clean(relative_path: str) -> None:
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
