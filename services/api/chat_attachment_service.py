from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

from .fs_atomic import atomic_write_json, atomic_write_text


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_MESSAGE = 5
MAX_TOTAL_SIZE_BYTES = 30 * 1024 * 1024
MAX_ATTACHMENT_CONTEXT_CHARS = 12000

_ATTACHMENT_ID_PATTERN = re.compile(r"^att_[a-f0-9]{8,32}$")
_ALLOWED_SUFFIXES = {
    ".md",
    ".markdown",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".xls",
    ".xlsx",
}


class ChatAttachmentError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class ChatAttachmentDeps:
    uploads_dir: Path
    sanitize_filename: Callable[[str], str]
    save_upload_file: Callable[[Any, Path], Awaitable[int]]
    extract_text_from_file: Callable[[Path, str, str], str]
    xlsx_to_table_preview: Callable[[Path], str]
    xls_to_table_preview: Callable[[Path], str]
    now_iso: Callable[[], str]
    uuid_hex: Callable[[], str]


def _attachments_root(uploads_dir: Path) -> Path:
    root = (uploads_dir / "chat_attachments").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalize_role(role: Optional[str]) -> str:
    return str(role or "").strip().lower()


def _safe_attachment_id(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if not _ATTACHMENT_ID_PATTERN.match(value):
        raise ChatAttachmentError(400, f"invalid attachment_id: {raw}")
    return value


def _attachment_dir(uploads_dir: Path, attachment_id: str) -> Path:
    root = _attachments_root(uploads_dir)
    aid = _safe_attachment_id(attachment_id)
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        raise ChatAttachmentError(400, "invalid attachment_id")
    return target


def _read_meta(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_meta(path: Path, payload: Dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def _detect_upload_size(upload: Any) -> Optional[int]:
    file_obj = getattr(upload, "file", None)
    if file_obj is None:
        return None
    try:
        current = file_obj.tell()
        file_obj.seek(0, 2)
        size = int(file_obj.tell())
        file_obj.seek(current)
        if size < 0:
            return None
        return size
    except Exception:
        return None


def _owner_matches(
    meta: Dict[str, Any],
    *,
    role: str,
    teacher_id: str,
    student_id: str,
    session_id: str,
) -> bool:
    return (
        str(meta.get("role") or "") == role
        and str(meta.get("teacher_id") or "") == teacher_id
        and str(meta.get("student_id") or "") == student_id
        and str(meta.get("session_id") or "") == session_id
    )


def _extract_attachment_ids(raw: Sequence[Any]) -> List[str]:
    ids: List[str] = []
    seen: set[str] = set()
    for item in raw:
        value = str(item or "").strip().lower()
        if not value:
            continue
        if value in seen:
            continue
        ids.append(value)
        seen.add(value)
    return ids


def _to_public_item(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "attachment_id": str(meta.get("attachment_id") or ""),
        "file_name": str(meta.get("file_name") or ""),
        "size_bytes": int(meta.get("size_bytes") or 0),
        "content_type": str(meta.get("content_type") or ""),
        "status": str(meta.get("status") or "unknown"),
        "error_code": str(meta.get("error_code") or ""),
        "error_detail": str(meta.get("error_detail") or ""),
    }


async def upload_chat_attachments(
    *,
    role: str,
    teacher_id: Optional[str],
    student_id: Optional[str],
    session_id: Optional[str],
    request_id: Optional[str],
    files: Sequence[Any],
    language: str = "zh",
    ocr_mode: str = "FREE_OCR",
    deps: ChatAttachmentDeps,
) -> Dict[str, Any]:
    role_norm = _normalize_role(role)
    if role_norm not in {"teacher", "student"}:
        raise ChatAttachmentError(400, "role must be teacher or student")
    teacher_value = str(teacher_id or "").strip() if role_norm == "teacher" else ""
    student_value = str(student_id or "").strip() if role_norm == "student" else ""
    session_value = str(session_id or "").strip() or "main"
    items = [item for item in files if item is not None]
    if not items:
        raise ChatAttachmentError(400, "至少上传一个文件")
    if len(items) > MAX_FILES_PER_MESSAGE:
        raise ChatAttachmentError(400, f"单条消息最多上传 {MAX_FILES_PER_MESSAGE} 个文件")

    known_total = 0
    for item in items:
        known_size = _detect_upload_size(item)
        if known_size is None:
            continue
        if known_size > MAX_FILE_SIZE_BYTES:
            raise ChatAttachmentError(400, "单个文件大小不能超过 10MB")
        known_total += known_size
    if known_total > MAX_TOTAL_SIZE_BYTES:
        raise ChatAttachmentError(400, "单条消息文件总大小不能超过 30MB")

    root = _attachments_root(deps.uploads_dir)
    total_written = 0
    attachments: List[Dict[str, Any]] = []
    created_dirs: List[Path] = []

    try:
        for upload in items:
            raw_name = str(getattr(upload, "filename", "") or "")
            file_name = deps.sanitize_filename(raw_name)
            if not file_name:
                raise ChatAttachmentError(400, "文件名不能为空")
            suffix = Path(file_name).suffix.lower()
            if suffix not in _ALLOWED_SUFFIXES:
                raise ChatAttachmentError(400, f"不支持的文件类型: {suffix or file_name}")

            attachment_id = f"att_{deps.uuid_hex()[:16]}"
            attachment_dir = (root / attachment_id).resolve()
            attachment_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.append(attachment_dir)
            source_path = attachment_dir / file_name

            size_bytes = int(await deps.save_upload_file(upload, source_path))
            total_written += size_bytes
            if size_bytes > MAX_FILE_SIZE_BYTES:
                raise ChatAttachmentError(400, "单个文件大小不能超过 10MB")
            if total_written > MAX_TOTAL_SIZE_BYTES:
                raise ChatAttachmentError(400, "单条消息文件总大小不能超过 30MB")

            content_type = str(getattr(upload, "content_type", "") or "")
            extracted_text = ""
            status = "ready"
            error_code = ""
            error_detail = ""
            try:
                if suffix == ".xlsx":
                    extracted_text = deps.xlsx_to_table_preview(source_path)
                elif suffix == ".xls":
                    extracted_text = deps.xls_to_table_preview(source_path)
                else:
                    extracted_text = deps.extract_text_from_file(source_path, language, ocr_mode)
                if not str(extracted_text or "").strip():
                    status = "failed"
                    error_code = "extract_empty"
                    error_detail = "附件解析结果为空"
                else:
                    atomic_write_text(attachment_dir / "extracted.txt", str(extracted_text), encoding="utf-8")
            except Exception as exc:
                status = "failed"
                error_code = "extract_failed"
                error_detail = str(exc)[:200]

            meta = {
                "attachment_id": attachment_id,
                "role": role_norm,
                "teacher_id": teacher_value,
                "student_id": student_value,
                "session_id": session_value,
                "request_id": str(request_id or "").strip(),
                "file_name": file_name,
                "size_bytes": size_bytes,
                "content_type": content_type,
                "status": status,
                "error_code": error_code,
                "error_detail": error_detail,
                "created_at": deps.now_iso(),
                "updated_at": deps.now_iso(),
            }
            _write_meta(attachment_dir / "meta.json", meta)
            attachments.append(_to_public_item(meta))
    except Exception:
        for attachment_dir in created_dirs:
            shutil.rmtree(attachment_dir, ignore_errors=True)
        raise

    return {
        "ok": True,
        "attachments": attachments,
        "limits": {
            "max_files_per_message": MAX_FILES_PER_MESSAGE,
            "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
            "max_total_size_bytes": MAX_TOTAL_SIZE_BYTES,
        },
    }


def get_chat_attachment_status(
    *,
    role: str,
    teacher_id: Optional[str],
    student_id: Optional[str],
    session_id: Optional[str],
    attachment_ids: Sequence[Any],
    deps: ChatAttachmentDeps,
) -> Dict[str, Any]:
    role_norm = _normalize_role(role)
    if role_norm not in {"teacher", "student"}:
        raise ChatAttachmentError(400, "role must be teacher or student")
    teacher_value = str(teacher_id or "").strip() if role_norm == "teacher" else ""
    student_value = str(student_id or "").strip() if role_norm == "student" else ""
    session_value = str(session_id or "").strip() or "main"
    ids = _extract_attachment_ids(attachment_ids)
    items: List[Dict[str, Any]] = []
    for raw_id in ids:
        try:
            attachment_dir = _attachment_dir(deps.uploads_dir, raw_id)
        except ChatAttachmentError:
            items.append(
                {
                    "attachment_id": raw_id,
                    "status": "invalid",
                    "error_code": "invalid_attachment_id",
                    "error_detail": "attachment_id 格式不合法",
                }
            )
            continue
        meta = _read_meta(attachment_dir / "meta.json")
        if not meta:
            items.append(
                {
                    "attachment_id": raw_id,
                    "status": "not_found",
                    "error_code": "not_found",
                    "error_detail": "附件不存在",
                }
            )
            continue
        if not _owner_matches(
            meta,
            role=role_norm,
            teacher_id=teacher_value,
            student_id=student_value,
            session_id=session_value,
        ):
            items.append(
                {
                    "attachment_id": raw_id,
                    "status": "forbidden",
                    "error_code": "forbidden_attachment",
                    "error_detail": "无权访问该附件",
                }
            )
            continue
        items.append(_to_public_item(meta))
    return {"ok": True, "attachments": items}


def delete_chat_attachment(
    *,
    role: str,
    teacher_id: Optional[str],
    student_id: Optional[str],
    session_id: Optional[str],
    attachment_id: str,
    deps: ChatAttachmentDeps,
) -> Dict[str, Any]:
    role_norm = _normalize_role(role)
    if role_norm not in {"teacher", "student"}:
        raise ChatAttachmentError(400, "role must be teacher or student")
    teacher_value = str(teacher_id or "").strip() if role_norm == "teacher" else ""
    student_value = str(student_id or "").strip() if role_norm == "student" else ""
    session_value = str(session_id or "").strip() or "main"
    attachment_dir = _attachment_dir(deps.uploads_dir, attachment_id)
    meta = _read_meta(attachment_dir / "meta.json")
    if not meta:
        return {"ok": True, "deleted": False}
    if not _owner_matches(
        meta,
        role=role_norm,
        teacher_id=teacher_value,
        student_id=student_value,
        session_id=session_value,
    ):
        raise ChatAttachmentError(403, "forbidden_attachment")
    shutil.rmtree(attachment_dir, ignore_errors=True)
    return {"ok": True, "deleted": True}


def resolve_chat_attachment_context(
    *,
    role: str,
    teacher_id: Optional[str],
    student_id: Optional[str],
    session_id: Optional[str],
    attachment_ids: Sequence[Any],
    deps: ChatAttachmentDeps,
    max_chars: int = MAX_ATTACHMENT_CONTEXT_CHARS,
) -> Dict[str, Any]:
    role_norm = _normalize_role(role)
    if role_norm not in {"teacher", "student"}:
        return {"attachment_context": "", "warnings": ["invalid_role"], "ready_attachment_ids": []}
    teacher_value = str(teacher_id or "").strip() if role_norm == "teacher" else ""
    student_value = str(student_id or "").strip() if role_norm == "student" else ""
    session_value = str(session_id or "").strip() or "main"

    ids = _extract_attachment_ids(attachment_ids)
    warnings: List[str] = []
    ready_ids: List[str] = []
    blocks: List[str] = []
    for idx, raw_id in enumerate(ids, start=1):
        try:
            attachment_dir = _attachment_dir(deps.uploads_dir, raw_id)
        except ChatAttachmentError:
            warnings.append(f"{raw_id}:invalid_attachment_id")
            continue
        meta = _read_meta(attachment_dir / "meta.json")
        if not meta:
            warnings.append(f"{raw_id}:not_found")
            continue
        if not _owner_matches(
            meta,
            role=role_norm,
            teacher_id=teacher_value,
            student_id=student_value,
            session_id=session_value,
        ):
            warnings.append(f"{raw_id}:forbidden_attachment")
            continue
        if str(meta.get("status") or "") != "ready":
            code = str(meta.get("error_code") or "not_ready")
            warnings.append(f"{raw_id}:{code}")
            continue
        extracted_path = attachment_dir / "extracted.txt"
        if not extracted_path.exists():
            warnings.append(f"{raw_id}:missing_extracted")
            continue
        try:
            text = extracted_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            text = ""
        if not text:
            warnings.append(f"{raw_id}:extract_empty")
            continue
        file_name = str(meta.get("file_name") or "unknown")
        block = f"[附件 #{idx}: {file_name}]\n{text}"
        blocks.append(block)
        ready_ids.append(raw_id)

    combined = "\n\n".join(blocks).strip()
    truncated = False
    if len(combined) > max_chars:
        combined = combined[:max_chars].rstrip() + "…"
        truncated = True
    if truncated:
        warnings.append("attachment_context_truncated")
    return {
        "attachment_context": combined,
        "warnings": warnings,
        "ready_attachment_ids": ready_ids,
    }
