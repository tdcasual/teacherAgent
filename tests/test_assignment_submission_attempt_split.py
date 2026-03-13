from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.api.assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    compute_submission_attempt,
)


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


def test_assignment_submission_attempt_hotspot_removed() -> None:
    target = "services/api/assignment_submission_attempt_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def compute_submission_attempt(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_compute_submission_attempt_uses_report_mtime_when_name_has_no_timestamp(
    tmp_path: Path,
) -> None:
    deps = AssignmentSubmissionAttemptDeps(
        student_submissions_dir=tmp_path / "student_submissions",
        grade_count_conf_threshold=0.8,
    )
    attempt_dir = tmp_path / "attempts" / "submission_misc"
    report_path = attempt_dir / "grading_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "graded_total": 1,
                "correct": 1,
                "ungraded": 0,
                "items": [{"status": "matched", "confidence": 0.95, "score": 2}],
            }
        ),
        encoding="utf-8",
    )

    result = compute_submission_attempt(attempt_dir, deps=deps)

    assert result is not None
    assert result["submitted_at"]
