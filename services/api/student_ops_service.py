from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from .upload_limits import UploadLimitError, save_limited_uploads

_STUDENT_ALLOWED_SUFFIXES = {".pdf", ".png", ".jpeg", ".jpg", ".webp", ".txt", ".md", ".csv"}
_STUDENT_MIME_BY_SUFFIX = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".csv": {"text/csv", "text/plain", "application/csv"},
}


@dataclass(frozen=True)
class StudentOpsDeps:
    uploads_dir: Path
    app_root: Path
    sanitize_filename: Callable[[str], str]
    save_upload_file: Callable[[Any, Path], Awaitable[int]]
    run_script: Callable[[List[str]], str]
    student_candidates_by_name: Callable[[str], List[Dict[str, Any]]]
    normalize: Callable[[str], str]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


async def upload_files(files: List[Any], *, deps: StudentOpsDeps) -> Dict[str, Any]:
    deps.uploads_dir.mkdir(parents=True, exist_ok=True)
    try:
        saved_paths = await save_limited_uploads(
            files,
            deps.uploads_dir,
            suffixes=_STUDENT_ALLOWED_SUFFIXES,
            mimes=_STUDENT_MIME_BY_SUFFIX,
            sanitize_filename=deps.sanitize_filename,
        )
    except UploadLimitError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"saved": [str(path) for path in saved_paths]}


def update_profile(
    *,
    student_id: str,
    weak_kp: Optional[str] = "",
    strong_kp: Optional[str] = "",
    medium_kp: Optional[str] = "",
    next_focus: Optional[str] = "",
    interaction_note: Optional[str] = "",
    deps: StudentOpsDeps,
) -> Dict[str, Any]:
    script = deps.app_root / "skills" / "physics-student-coach" / "scripts" / "update_profile.py"
    args = [
        "python3",
        str(script),
        "--student-id",
        student_id,
        "--weak-kp",
        weak_kp or "",
        "--strong-kp",
        strong_kp or "",
        "--medium-kp",
        medium_kp or "",
        "--next-focus",
        next_focus or "",
        "--interaction-note",
        interaction_note or "",
    ]
    out = deps.run_script(args)
    return {"ok": True, "output": out}


def verify_student(name: str, class_name: Optional[str], *, deps: StudentOpsDeps) -> Dict[str, Any]:
    name = (name or "").strip()
    class_name = (class_name or "").strip()
    if not name:
        return {"ok": False, "error": "missing_name", "message": "请先输入姓名。"}
    candidates = deps.student_candidates_by_name(name)
    if class_name:
        class_norm = deps.normalize(class_name)
        candidates = [c for c in candidates if deps.normalize(c.get("class_name", "")) == class_norm]
    if not candidates:
        deps.diag_log("student.verify.not_found", {"name": name, "class_name": class_name})
        return {"ok": False, "error": "not_found", "message": "未找到该学生，请检查姓名或班级。"}
    if len(candidates) > 1:
        deps.diag_log(
            "student.verify.multiple",
            {"name": name, "class_name": class_name, "candidates": candidates[:10]},
        )
        return {
            "ok": False,
            "error": "multiple",
            "message": "同名学生，请补充班级。",
            "candidates": candidates[:10],
        }
    candidate = candidates[0]
    deps.diag_log("student.verify.ok", candidate)
    return {"ok": True, "student": candidate}
