from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Mapping, Optional, Sequence

MAX_FILES = 20
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024
STREAM_CHUNK_SIZE = 1024 * 1024


class UploadLimitError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def unique_dest_path(dest: Path) -> Path:
    dest = Path(dest)
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    index = 1
    while index < 10000:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
    raise UploadLimitError(400, "无法生成唯一文件名")


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


def normalize_content_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if ";" in raw:
        raw = raw.split(";", 1)[0].strip()
    return raw


def _sanitized_filename(upload: Any, sanitize_filename: Callable[[str], str] | None) -> str:
    raw = str(getattr(upload, "filename", "") or "")
    if sanitize_filename is not None:
        return str(sanitize_filename(raw) or "")
    return Path(raw).name


def _assert_suffix_and_mime(
    filename: str,
    content_type: Any,
    *,
    suffixes: set[str],
    mimes: Mapping[str, set[str]],
) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in suffixes:
        raise UploadLimitError(400, f"不支持的文件类型: {suffix or filename}")
    allowed = mimes.get(suffix) or set()
    mime = normalize_content_type(content_type)
    if mime not in allowed:
        raise UploadLimitError(400, "文件类型与 MIME 不一致")
    return suffix


def _assert_known_size(known: int, known_total: int) -> int:
    if known > MAX_FILE_BYTES:
        raise UploadLimitError(400, "单个文件大小不能超过 20MB")
    next_total = known_total + known
    if next_total > MAX_TOTAL_BYTES:
        raise UploadLimitError(400, "单次上传总大小不能超过 80MB")
    return next_total


def enforce_upload_limits(
    files: Sequence[Any],
    *,
    suffixes: set[str],
    mimes: Mapping[str, set[str]],
    sanitize_filename: Callable[[str], str] | None = None,
) -> list[tuple[Any, str]]:
    items = [item for item in (files or []) if item is not None]
    if len(items) > MAX_FILES:
        raise UploadLimitError(400, f"最多上传 {MAX_FILES} 个文件")
    prepared: list[tuple[Any, str]] = []
    known_total = 0
    for upload in items:
        known = detect_upload_size(upload)
        if known is not None:
            known_total = _assert_known_size(known, known_total)
        filename = _sanitized_filename(upload, sanitize_filename)
        if not filename:
            continue
        _assert_suffix_and_mime(
            filename,
            getattr(upload, "content_type", ""),
            suffixes=suffixes,
            mimes=mimes,
        )
        prepared.append((upload, filename))
    return prepared


def _seek_start(file_obj: Any) -> None:
    seek = getattr(file_obj, "seek", None)
    if not callable(seek):
        return
    try:
        seek(0)
    except (OSError, ValueError, TypeError):
        return


async def _read_chunk(source: Any, chunk_size: int) -> bytes:
    chunk = source.read(chunk_size)
    if inspect.isawaitable(chunk):
        chunk = await chunk
    if not chunk:
        return b""
    if isinstance(chunk, str):
        return chunk.encode("utf-8")
    return bytes(chunk)


async def _iter_chunks(upload: Any, chunk_size: int) -> AsyncIterator[bytes]:
    file_obj = getattr(upload, "file", None)
    if file_obj is not None:
        _seek_start(file_obj)
        reader: Any = file_obj
    else:
        reader = upload
        if not callable(getattr(reader, "read", None)):
            return
    while True:
        chunk = await _read_chunk(reader, chunk_size)
        if not chunk:
            break
        yield chunk


def _assert_written_within_caps(written: int, counters: dict[str, int]) -> None:
    if written > MAX_FILE_BYTES:
        raise UploadLimitError(400, "单个文件大小不能超过 20MB")
    if int(counters.get("total", 0)) + written > MAX_TOTAL_BYTES:
        raise UploadLimitError(400, "单次上传总大小不能超过 80MB")


def _precheck_known_write(upload: Any, counters: dict[str, int]) -> None:
    known = detect_upload_size(upload)
    if known is None:
        return
    _assert_known_size(known, int(counters.get("total", 0)))


async def save_upload_streaming(
    upload: Any,
    dest: Path,
    *,
    counters: dict[str, int],
    chunk_size: int = STREAM_CHUNK_SIZE,
) -> int:
    _precheck_known_write(upload, counters)
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dest.open("wb") as out:
            async for chunk in _iter_chunks(upload, chunk_size):
                written += len(chunk)
                _assert_written_within_caps(written, counters)
                out.write(chunk)
    except (UploadLimitError, OSError):
        dest.unlink(missing_ok=True)
        raise
    counters["total"] = int(counters.get("total", 0)) + written
    return written


async def save_limited_uploads(
    files: Sequence[Any],
    target_dir: Path,
    *,
    suffixes: set[str],
    mimes: Mapping[str, set[str]],
    sanitize_filename: Callable[[str], str] | None = None,
    chunk_size: int = STREAM_CHUNK_SIZE,
) -> list[Path]:
    prepared = enforce_upload_limits(
        files,
        suffixes=suffixes,
        mimes=mimes,
        sanitize_filename=sanitize_filename,
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    counters = {"total": 0}
    saved: list[Path] = []
    try:
        for upload, filename in prepared:
            dest = unique_dest_path(target_dir / filename)
            await save_upload_streaming(upload, dest, counters=counters, chunk_size=chunk_size)
            saved.append(dest)
        return saved
    except (UploadLimitError, OSError):
        for path in saved:
            path.unlink(missing_ok=True)
        raise
