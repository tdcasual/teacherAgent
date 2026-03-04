from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException


def _default_sanitize_filename(name: str) -> str:
    return Path(str(name or "").strip()).name


_SAFE_ID_RE = re.compile(r"^[\w-]+$")


def _require_safe_id(value: str, field: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail=f"{field} is required")
    if not _SAFE_ID_RE.fullmatch(token):
        raise HTTPException(status_code=400, detail=f"invalid_{field}")
    return token


@dataclass(frozen=True)
class StudentSubmitDeps:
    uploads_dir: Path
    app_root: Path
    student_submissions_dir: Path
    run_script: Callable[[list[str]], str]
    compute_assignment_progress: Callable[[str, bool], Dict[str, Any]]
    student_memory_auto_propose_from_assignment_evidence: Callable[..., Dict[str, Any]]
    resolve_teacher_id: Callable[[Optional[str]], str]
    diag_log: Callable[[str, Dict[str, Any]], None]
    sanitize_filename: Callable[[str], str] = _default_sanitize_filename


def _find_student_evidence(
    *,
    progress: Dict[str, Any],
    student_id: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(progress, dict) or not bool(progress.get("ok")):
        return None
    students = progress.get("students")
    if not isinstance(students, list):
        return None
    for item in students:
        if not isinstance(item, dict):
            continue
        if str(item.get("student_id") or "").strip() != student_id:
            continue
        evidence = item.get("evidence")
        if isinstance(evidence, dict):
            return evidence
        return None
    return None


async def submit(
    *,
    student_id: str,
    files: List[Any],
    assignment_id: Optional[str],
    auto_assignment: bool,
    deps: StudentSubmitDeps,
) -> Dict[str, Any]:
    deps.uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_student_id = _require_safe_id(student_id, "student_id")
    safe_assignment_id: Optional[str] = None

    file_paths: List[str] = []
    for upload_file in files:
        filename = deps.sanitize_filename(getattr(upload_file, "filename", ""))
        if not filename:
            continue
        dest = deps.uploads_dir / filename
        dest.write_bytes(await upload_file.read())
        file_paths.append(str(dest))

    script = deps.app_root / "scripts" / "grade_submission.py"
    args = [
        "python3",
        str(script),
        "--student-id",
        safe_student_id,
        "--out-dir",
        str(deps.student_submissions_dir),
        "--files",
        *file_paths,
    ]
    if assignment_id:
        safe_assignment_id = _require_safe_id(assignment_id, "assignment_id")
        args += ["--assignment-id", safe_assignment_id]
    if auto_assignment or not assignment_id:
        args += ["--auto-assignment"]

    out = deps.run_script(args)
    if safe_assignment_id:
        try:
            progress = deps.compute_assignment_progress(safe_assignment_id, True)
            evidence = _find_student_evidence(progress=progress, student_id=safe_student_id)
            if evidence:
                teacher_id = str(deps.resolve_teacher_id(None) or "").strip() or None
                auto = deps.student_memory_auto_propose_from_assignment_evidence(
                    teacher_id=teacher_id,
                    student_id=safe_student_id,
                    assignment_id=safe_assignment_id,
                    evidence=evidence,
                    request_id=None,
                )
                if bool(auto.get("created")):
                    deps.diag_log(
                        "student.memory.assignment_evidence.proposed",
                        {
                            "teacher_id": str(auto.get("teacher_id") or teacher_id or ""),
                            "student_id": safe_student_id,
                            "assignment_id": safe_assignment_id,
                            "proposal_id": str(auto.get("proposal_id") or ""),
                            "memory_type": str(auto.get("memory_type") or ""),
                        },
                    )
        except Exception as exc:  # policy: allowed-broad-except
            deps.diag_log(
                "student.memory.assignment_evidence.failed",
                {
                    "student_id": safe_student_id,
                    "assignment_id": safe_assignment_id,
                    "error": str(exc)[:200],
                },
            )
    return {"ok": True, "output": out}
