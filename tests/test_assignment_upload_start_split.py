from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from services.api.assignment_upload_start_service import (
    AssignmentUploadStartDeps,
    start_assignment_upload,
)


class _FakeUpload:
    def __init__(self, filename: str) -> None:
        self.filename = filename


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


def _deps(root: Path, *, writes: dict[str, dict] | None = None) -> AssignmentUploadStartDeps:
    async def save_upload_file(upload: _FakeUpload, dest: Path) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"from:{upload.filename}", encoding="utf-8")
        return len(upload.filename)

    return AssignmentUploadStartDeps(
        new_job_id=lambda: "job_fixed_001",
        parse_date_str=lambda value: str(value or "2026-02-08"),
        upload_job_path=lambda job_id: root / "assignment_jobs" / job_id,
        sanitize_filename=lambda name: str(name or "").strip(),
        save_upload_file=save_upload_file,
        parse_ids_value=lambda value: [item.strip() for item in str(value or "").split(",") if item.strip()],
        resolve_scope=lambda scope, student_ids, class_name: str(scope or "public"),
        normalize_due_at=lambda value: str(value or ""),
        now_iso=lambda: "2026-02-08T12:00:00",
        write_upload_job=lambda job_id, updates, overwrite=False: (
            (writes if writes is not None else {}).setdefault(
                job_id,
                {**updates, "_overwrite": overwrite},
            )
        ),
        enqueue_upload_job=lambda job_id: None,
        diag_log=lambda event, payload=None: None,
    )


def test_assignment_upload_start_hotspot_removed() -> None:
    target = "services/api/assignment_upload_start_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "async def start_assignment_upload(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_start_upload_keeps_image_mode_when_only_answer_is_pdf(tmp_path: Path) -> None:
    writes: dict[str, dict] = {}
    result = asyncio.run(
        start_assignment_upload(
            assignment_id="HW_1",
            date="2026-02-08",
            due_at="2026-02-09T20:00:00",
            scope="class",
            class_name="高二2403班",
            student_ids="",
            files=[_FakeUpload("paper.png")],
            answer_files=[_FakeUpload("answer.pdf")],
            ocr_mode="FREE_OCR",
            language="zh",
            deps=_deps(tmp_path, writes=writes),
        )
    )

    assert result["ok"] is True
    assert writes["job_fixed_001"]["delivery_mode"] == "image"
