from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
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
    sanitize_filename: Callable[[str], str] = _default_sanitize_filename


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
        args += ["--assignment-id", _require_safe_id(assignment_id, "assignment_id")]
    if auto_assignment or not assignment_id:
        args += ["--auto-assignment"]

    out = deps.run_script(args)
    return {"ok": True, "output": out}
