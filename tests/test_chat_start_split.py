from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.api.chat_start_service import _normalize_analysis_target_payload


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


class _TargetPayload:
    def model_dump(self, *, exclude_none: bool = True) -> dict:
        assert exclude_none is True
        return {
            "target_type": "report",
            "report_id": "report_42",
            "source_domain": "survey",
            "teacher_id": "teacher_1",
        }


def test_chat_start_analysis_target_hotspot_removed() -> None:
    target = "services/api/chat_start_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _normalize_analysis_target_payload(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_normalize_analysis_target_payload_uses_report_id_as_target_id() -> None:
    result = _normalize_analysis_target_payload(_TargetPayload())

    assert result == {
        "target_type": "report",
        "target_id": "report_42",
        "source_domain": "survey",
        "report_id": "report_42",
        "teacher_id": "teacher_1",
    }
