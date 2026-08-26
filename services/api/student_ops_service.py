from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, NoReturn, Optional

from fastapi import HTTPException

from .upload_limits import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES

STUDENT_ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md", ".csv"}
_UNIQUE_DEST_TRIES = 32


class UploadLimitError(Exception):
    def __init__(self, error: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = int(status_code)
        self.error = str(error)
        self.message = str(message)
        self.detail = {"error": self.error, "message": self.message}


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
    issue_student_candidate_id: Callable[[str], str]


def _name_taken(path: Path) -> bool:
    try:
        return path.exists(follow_symlinks=False)
    except OSError:
        return True


def unique_upload_dest(target_dir: Path, filename: str) -> Path:
    leaf = Path(str(filename or "")).name
    if leaf in {"", ".", ".."}:
        raise UploadLimitError("invalid_suffix", f"不支持的文件类型: {filename}")
    stem = Path(leaf).stem
    suffix = Path(leaf).suffix
    names = [leaf, f"{stem}-2{suffix}"]
    for index in range(_UNIQUE_DEST_TRIES + 2):
        if index < len(names):
            name = names[index]
        else:
            name = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
        dest = target_dir / name
        if _name_taken(dest):
            continue
        try:
            dest.touch(exist_ok=False)
        except FileExistsError:
            continue
        return dest
    raise UploadLimitError("too_many_files", "无法生成唯一文件名")


def detect_upload_size(upload: Any) -> Optional[int]:
    file_obj = getattr(upload, "file", None)
    if file_obj is None:
        return None
    tell = getattr(file_obj, "tell", None)
    seek = getattr(file_obj, "seek", None)
    if not callable(tell) or not callable(seek):
        return None
    try:
        current = tell()
        seek(0, 2)
        size = int(tell())
        seek(current)
    except (OSError, ValueError, TypeError):
        return None
    if size < 0:
        return None
    return size


def prepare_capped_uploads(
    files: Optional[List[Any]],
    *,
    sanitize_filename: Callable[[str], str],
    allowed_suffixes: set[str],
) -> List[tuple[Any, str]]:
    items = [item for item in (files or []) if item is not None]
    if len(items) > MAX_FILES:
        raise UploadLimitError("too_many_files", f"最多上传 {MAX_FILES} 个文件")
    prepared: List[tuple[Any, str]] = []
    known_total = 0
    for upload in items:
        filename = sanitize_filename(getattr(upload, "filename", "") or "")
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix not in allowed_suffixes:
            raise UploadLimitError("invalid_suffix", f"不支持的文件类型: {suffix or filename}")
        known_size = detect_upload_size(upload)
        if known_size is not None:
            if known_size > MAX_FILE_BYTES:
                raise UploadLimitError("file_too_large", "单个文件大小不能超过 20MB")
            known_total += known_size
        prepared.append((upload, filename))
    if known_total > MAX_TOTAL_BYTES:
        raise UploadLimitError("file_too_large", "单次上传总大小不能超过 80MB")
    return prepared


async def save_capped_uploads(
    files: Optional[List[Any]],
    *,
    target_dir: Path,
    sanitize_filename: Callable[[str], str],
    save_upload_file: Callable[[Any, Path], Awaitable[int]],
    allowed_suffixes: set[str],
) -> List[Path]:
    prepared = prepare_capped_uploads(
        files,
        sanitize_filename=sanitize_filename,
        allowed_suffixes=allowed_suffixes,
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    total_written = 0
    for upload, filename in prepared:
        dest = unique_upload_dest(target_dir, filename)
        written = await save_upload_file(upload, dest)
        if written is None:
            size_bytes = int(dest.stat().st_size)
        else:
            size_bytes = int(written)
        if size_bytes > MAX_FILE_BYTES:
            dest.unlink(missing_ok=True)
            raise UploadLimitError("file_too_large", "单个文件大小不能超过 20MB")
        total_written += size_bytes
        if total_written > MAX_TOTAL_BYTES:
            dest.unlink(missing_ok=True)
            raise UploadLimitError("file_too_large", "单次上传总大小不能超过 80MB")
        saved.append(dest)
    return saved


def raise_upload_limit_http(exc: UploadLimitError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def upload_files(files: List[Any], *, deps: StudentOpsDeps) -> Dict[str, Any]:
    deps.uploads_dir.mkdir(parents=True, exist_ok=True)
    try:
        saved = await save_capped_uploads(
            files,
            target_dir=deps.uploads_dir,
            sanitize_filename=deps.sanitize_filename,
            save_upload_file=deps.save_upload_file,
            allowed_suffixes=STUDENT_ALLOWED_SUFFIXES,
        )
    except UploadLimitError as exc:
        raise_upload_limit_http(exc)
    return {"saved": [str(path) for path in saved]}


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


def _public_verify_candidate(
    candidate: Dict[str, Any],
    issue_student_candidate_id: Callable[[str], str],
) -> Dict[str, Any]:
    sid = str(candidate.get("student_id") or "").strip()
    return {
        "candidate_id": issue_student_candidate_id(sid) if sid else "",
        "student": {
            "student_name": str(candidate.get("student_name") or ""),
            "class_name": str(candidate.get("class_name") or ""),
        },
    }


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
    public_candidates = [
        _public_verify_candidate(item, deps.issue_student_candidate_id) for item in candidates
    ]
    if len(public_candidates) > 1:
        deps.diag_log(
            "student.verify.multiple",
            {"name": name, "class_name": class_name, "candidates": candidates[:10]},
        )
        return {
            "ok": False,
            "error": "multiple",
            "message": "同名学生，请补充班级。",
            "candidates": public_candidates[:10],
        }
    candidate = candidates[0]
    deps.diag_log("student.verify.ok", candidate)
    return {"ok": True, **public_candidates[0]}
