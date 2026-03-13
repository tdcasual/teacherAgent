from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _issues(path: str) -> list[dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            path,
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=10",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


def test_student_memory_hotspots_removed() -> None:
    target = "services/api/student_memory_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _load_existing_proposals(" in source
    assert "def _resolve_auto_proposal_conflict(" in source
    assert "def _create_auto_proposal(" in source
    assert "def _list_proposal_files(" in source
    assert "def _proposal_matches_filters(" in source
    assert "def _normalize_listed_proposal(" in source
    assert "def student_memory_auto_propose_from_turn_api(" in source
    assert "def student_memory_auto_propose_from_assignment_evidence_api(" in source
    assert "def list_proposals_api(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
