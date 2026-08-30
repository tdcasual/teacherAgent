from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.api.chat_job_processing.compute import _job_actor_id
from services.api.chat_job_processing_service import _normalize_workflow_resolution_payload


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


def test_job_actor_id_uses_student_id_for_student_jobs() -> None:
    assert _job_actor_id({"role": "student", "student_id": "S_WU", "teacher_id": "t_zhang"}) == "S_WU"
    assert _job_actor_id({"role": "teacher", "student_id": "S_WU", "teacher_id": "t_zhang"}) == "t_zhang"
    assert _job_actor_id({"role": "student"}) is None


def test_chat_job_processing_workflow_payload_hotspot_removed() -> None:
    target = "services/api/chat_job_processing_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _normalize_workflow_resolution_payload(" in source
    assert "def compute_chat_reply_sync(" in source
    history_source = Path("services/api/chat_job_processing/history.py").read_text(encoding="utf-8")
    assert "def _run_student_post_done_side_effects(" in history_source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_normalize_workflow_resolution_payload_keeps_expected_shape() -> None:
    payload = _normalize_workflow_resolution_payload(
        " homework-generator ",
        "teacher-assignment-ops",
        {
            "reason": "auto_rule.teacher",
            "confidence": "0.64",
            "candidates": [
                {
                    "skill_id": "teacher-assignment-ops",
                    "score": "12",
                    "hits": ["考试", "分析", "", None],
                },
                {
                    "skill_id": "homework-generator",
                    "score": "oops",
                    "hits": list("123456789"),
                },
                {"skill_id": "", "score": 3},
                "invalid",
            ],
        },
    )

    assert payload == {
        "requested_skill_id": "homework-generator",
        "effective_skill_id": "teacher-assignment-ops",
        "reason": "auto_rule.teacher",
        "confidence": 0.64,
        "candidates": [
            {"skill_id": "teacher-assignment-ops", "score": 12, "hits": ["考试", "分析"]},
            {"skill_id": "homework-generator", "hits": ["1", "2", "3", "4", "5", "6"]},
        ],
        "resolution_mode": "auto",
        "auto_selected": True,
        "requested_rewritten": True,
    }
