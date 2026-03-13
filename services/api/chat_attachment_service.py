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


def _actor_values(
    role: Optional[str],
    *,
    teacher_id: Optional[str],
    student_id: Optional[str],
    session_id: Optional[str],
) -> tuple[str, str, str, str]:
    role_norm = _normalize_role(role)
    teacher_value = str(teacher_id or "").strip() if role_norm == "teacher" else ""
    student_value = str(student_id or "").strip() if role_norm == "student" else ""
    session_value = str(session_id or "").strip() or "main"
    return role_norm, teacher_value, student_value, session_value


def _upload_items(files: Sequence[Any]) -> List[Any]:
    items = [item for item in files if item is not None]
    if not items:
        raise ChatAttachmentError(400, "至少上传一个文件")
    if len(items) > MAX_FILES_PER_MESSAGE:
        raise ChatAttachmentError(400, f"单条消息最多上传 {MAX_FILES_PER_MESSAGE} 个文件")
    return items


def _validate_known_upload_total(items: Sequence[Any]) -> None:
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


def _validated_attachment_name(upload: Any, *, deps: ChatAttachmentDeps) -> tuple[str, str]:
    raw_name = str(getattr(upload, "filename", "") or "")
    file_name = deps.sanitize_filename(raw_name)
    if not file_name:
        raise ChatAttachmentError(400, "文件名不能为空")
    suffix = Path(file_name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ChatAttachmentError(400, f"不支持的文件类型: {suffix or file_name}")
    return file_name, suffix


def _new_attachment_dir(root: Path, *, deps: ChatAttachmentDeps) -> tuple[str, Path]:
    attachment_id = f"att_{deps.uuid_hex()[:16]}"
    attachment_dir = (root / attachment_id).resolve()
    attachment_dir.mkdir(parents=True, exist_ok=True)
    return attachment_id, attachment_dir


async def _write_attachment_source(
    upload: Any,
    source_path: Path,
    *,
    deps: ChatAttachmentDeps,
    total_written: int,
) -> tuple[int, int]:
    size_bytes = int(await deps.save_upload_file(upload, source_path))
    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise ChatAttachmentError(400, "单个文件大小不能超过 10MB")
    total_written += size_bytes
    if total_written > MAX_TOTAL_SIZE_BYTES:
        raise ChatAttachmentError(400, "单条消息文件总大小不能超过 30MB")
    return size_bytes, total_written


def _extract_attachment_result(
    source_path: Path,
    suffix: str,
    *,
    language: str,
    ocr_mode: str,
    deps: ChatAttachmentDeps,
) -> tuple[str, str, str]:
    try:
        if suffix == ".xlsx":
            extracted_text = deps.xlsx_to_table_preview(source_path)
        elif suffix == ".xls":
            extracted_text = deps.xls_to_table_preview(source_path)
        else:
            extracted_text = deps.extract_text_from_file(source_path, language, ocr_mode)
    except Exception as exc:
        return "", "extract_failed", str(exc)[:200]
    if not str(extracted_text or "").strip():
        return "", "extract_empty", "附件解析结果为空"
    return str(extracted_text), "", ""


def _build_attachment_meta(
    *,
    attachment_id: str,
    role_norm: str,
    teacher_value: str,
    student_value: str,
    session_value: str,
    request_id: Optional[str],
    file_name: str,
    size_bytes: int,
    content_type: str,
    error_code: str,
    error_detail: str,
    deps: ChatAttachmentDeps,
) -> Dict[str, Any]:
    status = "failed" if error_code else "ready"
    now_iso = deps.now_iso()
    return {
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
        "created_at": now_iso,
        "updated_at": now_iso,
    }


async def _create_attachment_item(
    upload: Any,
    *,
    attachment_id: str,
    attachment_dir: Path,
    file_name: str,
    suffix: str,
    role_norm: str,
    teacher_value: str,
    student_value: str,
    session_value: str,
    request_id: Optional[str],
    language: str,
    ocr_mode: str,
    deps: ChatAttachmentDeps,
    total_written: int,
) -> tuple[Dict[str, Any], int]:
    source_path = attachment_dir / file_name
    size_bytes, total_written = await _write_attachment_source(
        upload,
        source_path,
        deps=deps,
        total_written=total_written,
    )
    content_type = str(getattr(upload, "content_type", "") or "")
    extracted_text, error_code, error_detail = _extract_attachment_result(
        source_path,
        suffix,
        language=language,
        ocr_mode=ocr_mode,
        deps=deps,
    )
    if not error_code:
        atomic_write_text(attachment_dir / "extracted.txt", extracted_text, encoding="utf-8")
    meta = _build_attachment_meta(
        attachment_id=attachment_id,
        role_norm=role_norm,
        teacher_value=teacher_value,
        student_value=student_value,
        session_value=session_value,
        request_id=request_id,
        file_name=file_name,
        size_bytes=size_bytes,
        content_type=content_type,
        error_code=error_code,
        error_detail=error_detail,
        deps=deps,
    )
    _write_meta(attachment_dir / "meta.json", meta)
    return _to_public_item(meta), total_written


def _resolve_accessible_attachment(
    raw_id: str,
    *,
    role_norm: str,
    teacher_value: str,
    student_value: str,
    session_value: str,
    deps: ChatAttachmentDeps,
) -> tuple[Optional[Path], Optional[Dict[str, Any]], Optional[str]]:
    try:
        attachment_dir = _attachment_dir(deps.uploads_dir, raw_id)
    except ChatAttachmentError:
        return None, None, "invalid_attachment_id"
    meta = _read_meta(attachment_dir / "meta.json")
    if not meta:
        return attachment_dir, None, "not_found"
    if not _owner_matches(
        meta,
        role=role_norm,
        teacher_id=teacher_value,
        student_id=student_value,
        session_id=session_value,
    ):
        return attachment_dir, meta, "forbidden_attachment"
    return attachment_dir, meta, None


def _attachment_context_block(
    attachment_dir: Path,
    meta: Dict[str, Any],
    *,
    idx: int,
) -> tuple[Optional[str], Optional[str]]:
    if str(meta.get("status") or "") != "ready":
        return None, str(meta.get("error_code") or "not_ready")
    extracted_path = attachment_dir / "extracted.txt"
    if not extracted_path.exists():
        return None, "missing_extracted"
    try:
        text = extracted_path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        text = ""
    if not text:
        return None, "extract_empty"
    file_name = str(meta.get("file_name") or "unknown")
    return f"[附件 #{idx}: {file_name}]\n{text}", None


def _combine_attachment_context_blocks(blocks: List[str], max_chars: int) -> tuple[str, bool]:
    combined = "\n\n".join(blocks).strip()
    if len(combined) <= max_chars:
        return combined, False
    return combined[:max_chars].rstrip() + "…", True


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
    role_norm, teacher_value, student_value, session_value = _actor_values(
        role,
        teacher_id=teacher_id,
        student_id=student_id,
        session_id=session_id,
    )
    if role_norm not in {"teacher", "student"}:
        raise ChatAttachmentError(400, "role must be teacher or student")
    items = _upload_items(files)
    _validate_known_upload_total(items)

    root = _attachments_root(deps.uploads_dir)
    total_written = 0
    attachments: List[Dict[str, Any]] = []
    created_dirs: List[Path] = []

    try:
        for upload in items:
            file_name, suffix = _validated_attachment_name(upload, deps=deps)
            attachment_id, attachment_dir = _new_attachment_dir(root, deps=deps)
            created_dirs.append(attachment_dir)
            public_item, total_written = await _create_attachment_item(
                upload,
                attachment_id=attachment_id,
                attachment_dir=attachment_dir,
                file_name=file_name,
                suffix=suffix,
                role_norm=role_norm,
                teacher_value=teacher_value,
                student_value=student_value,
                session_value=session_value,
                request_id=request_id,
                language=language,
                ocr_mode=ocr_mode,
                deps=deps,
                total_written=total_written,
            )
            attachments.append(public_item)
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
    role_norm, teacher_value, student_value, session_value = _actor_values(
        role,
        teacher_id=teacher_id,
        student_id=student_id,
        session_id=session_id,
    )
    if role_norm not in {"teacher", "student"}:
        return {"attachment_context": "", "warnings": ["invalid_role"], "ready_attachment_ids": []}

    ids = _extract_attachment_ids(attachment_ids)
    warnings: List[str] = []
    ready_ids: List[str] = []
    blocks: List[str] = []
    for idx, raw_id in enumerate(ids, start=1):
        attachment_dir, meta, warning = _resolve_accessible_attachment(
            raw_id,
            role_norm=role_norm,
            teacher_value=teacher_value,
            student_value=student_value,
            session_value=session_value,
            deps=deps,
        )
        if warning:
            warnings.append(f"{raw_id}:{warning}")
            continue
        assert attachment_dir is not None
        assert meta is not None
        block, warning = _attachment_context_block(attachment_dir, meta, idx=idx)
        if warning:
            warnings.append(f"{raw_id}:{warning}")
            continue
        assert block is not None
        blocks.append(block)
        ready_ids.append(raw_id)

    combined, truncated = _combine_attachment_context_blocks(blocks, max_chars)
    if truncated:
        warnings.append("attachment_context_truncated")
    return {
        "attachment_context": combined,
        "warnings": warnings,
        "ready_attachment_ids": ready_ids,
    }
