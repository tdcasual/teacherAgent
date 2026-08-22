from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest

from services.api.assignment_upload_start_service import _ASSIGNMENT_ALLOWED_SUFFIXES
from services.api.exam_upload_start_service import _ALLOWED_PAPER_SUFFIXES, _ALLOWED_SCORE_SUFFIXES
from services.api.student_ops_service import STUDENT_ALLOWED_SUFFIXES, STUDENT_MIME_BY_SUFFIX
from services.api.student_submit_service import STUDENT_ALLOWED_SUFFIXES as SUBMIT_SUFFIXES
from services.api.student_submit_service import STUDENT_MIME_BY_SUFFIX as SUBMIT_MIMES
from services.api.upload_limits import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    UploadLimitError,
    enforce_upload_limits,
    save_upload_streaming,
    unique_dest_path,
)


class _Upload:
    def __init__(self, filename: str, payload: bytes, content_type: str):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(payload)

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            raise AssertionError("full read() is forbidden")
        return self.file.read(size)


class _SizedFile:
    def __init__(self, size: int):
        self._size = int(size)
        self._pos = 0

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 2:
            self._pos = self._size + int(offset)
        elif whence == 1:
            self._pos = self._pos + int(offset)
        else:
            self._pos = int(offset)
        return self._pos

    def read(self, n: int = -1) -> bytes:
        remaining = max(0, self._size - self._pos)
        take = remaining if n is None or n < 0 else min(int(n), remaining)
        self._pos += take
        return b"x" * take


class _SizedUpload:
    def __init__(self, filename: str, size: int, content_type: str):
        self.filename = filename
        self.content_type = content_type
        self.file = _SizedFile(size)

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            raise AssertionError("full read() is forbidden")
        return self.file.read(size)


_PDF_MIME = {"application/pdf"}
_PNG_MIME = {"image/png"}
_SAMPLE_MIMES = {".pdf": _PDF_MIME, ".png": _PNG_MIME}


def test_shared_numeric_caps() -> None:
    assert MAX_FILES == 20
    assert MAX_FILE_BYTES == 20 * 1024 * 1024
    assert MAX_TOTAL_BYTES == 80 * 1024 * 1024


def test_exam_and_assignment_import_shared_numeric_caps() -> None:
    from services.api import assignment_upload_start_service as assignment
    from services.api import exam_upload_start_service as exam
    from services.api import upload_limits as limits

    assert exam.MAX_FILES_PER_UPLOAD_FIELD is limits.MAX_FILES
    assert exam.MAX_UPLOAD_FILE_SIZE_BYTES is limits.MAX_FILE_BYTES
    assert exam.MAX_UPLOAD_TOTAL_SIZE_BYTES is limits.MAX_TOTAL_BYTES
    assert assignment.MAX_FILES_PER_UPLOAD_FIELD is limits.MAX_FILES
    assert assignment.MAX_UPLOAD_FILE_SIZE_BYTES is limits.MAX_FILE_BYTES
    assert assignment.MAX_UPLOAD_TOTAL_SIZE_BYTES is limits.MAX_TOTAL_BYTES


def test_exam_and_assignment_keep_wide_suffix_sets() -> None:
    assert {".xlsx", ".xls", ".csv"} <= _ALLOWED_SCORE_SUFFIXES
    assert {".bmp", ".tex", ".markdown"} <= _ALLOWED_PAPER_SUFFIXES
    assert {".bmp", ".tex", ".markdown"} <= _ASSIGNMENT_ALLOWED_SUFFIXES
    assert ".xlsx" not in _ASSIGNMENT_ALLOWED_SUFFIXES


def test_enforce_upload_limits_rejects_21st_file() -> None:
    files = [_Upload(f"p{i}.pdf", b"x", "application/pdf") for i in range(MAX_FILES + 1)]
    with pytest.raises(UploadLimitError) as ctx:
        enforce_upload_limits(files, suffixes={".pdf"}, mimes=_SAMPLE_MIMES)
    assert ctx.value.status_code == 400
    assert "20" in str(ctx.value.detail)


def test_enforce_upload_limits_rejects_known_oversize_file() -> None:
    upload = _SizedUpload("paper.pdf", MAX_FILE_BYTES + 1, "application/pdf")
    with pytest.raises(UploadLimitError) as ctx:
        enforce_upload_limits([upload], suffixes={".pdf"}, mimes=_SAMPLE_MIMES)
    assert ctx.value.status_code == 400
    assert "20MB" in str(ctx.value.detail)


def test_enforce_upload_limits_rejects_mime_mismatch() -> None:
    upload = _Upload("homework.pdf", b"%PDF", "image/jpeg")
    with pytest.raises(UploadLimitError) as ctx:
        enforce_upload_limits([upload], suffixes={".pdf"}, mimes=_SAMPLE_MIMES)
    assert ctx.value.status_code == 400


def test_student_endpoints_share_one_allowlist() -> None:
    assert SUBMIT_SUFFIXES is STUDENT_ALLOWED_SUFFIXES
    assert SUBMIT_MIMES is STUDENT_MIME_BY_SUFFIX


def test_empty_and_octet_stream_mime_fall_back_to_suffix() -> None:
    empty = _Upload("notes.md", b"# hi", "")
    octet = _Upload("notes.md", b"# hi", "application/octet-stream")
    for upload in (empty, octet):
        prepared = enforce_upload_limits(
            [upload],
            suffixes=STUDENT_ALLOWED_SUFFIXES,
            mimes=STUDENT_MIME_BY_SUFFIX,
        )
        assert len(prepared) == 1


def test_csv_accepts_excel_mime() -> None:
    upload = _Upload("scores.csv", b"a,b", "application/vnd.ms-excel")
    prepared = enforce_upload_limits(
        [upload],
        suffixes=STUDENT_ALLOWED_SUFFIXES,
        mimes=STUDENT_MIME_BY_SUFFIX,
    )
    assert len(prepared) == 1


def test_unique_dest_path_does_not_overwrite_original(tmp_path: Path) -> None:
    original = tmp_path / "a.pdf"
    original.write_bytes(b"original")
    dest = unique_dest_path(original)
    assert dest != original
    assert dest.name == "a_1.pdf"
    dest.write_bytes(b"new")
    assert original.read_bytes() == b"original"
    assert dest.read_bytes() == b"new"


def test_unique_dest_path_skips_symlink(tmp_path: Path) -> None:
    dest = tmp_path / "a.pdf"
    dest.symlink_to(tmp_path / "missing.pdf")
    assert unique_dest_path(dest).name == "a_1.pdf"


def test_save_upload_streaming_writes_chunks_and_counts(tmp_path: Path) -> None:
    dest = tmp_path / "paper.pdf"
    upload = _Upload("paper.pdf", b"abcdef", "application/pdf")
    counters = {"total": 0}

    async def _run() -> tuple[Path, int]:
        return await save_upload_streaming(upload, dest, counters=counters, chunk_size=2)

    used, written = asyncio.run(_run())
    assert written == 6
    assert counters["total"] == 6
    assert used.read_bytes() == b"abcdef"


def test_save_upload_streaming_rejects_over_max_file_bytes(tmp_path: Path) -> None:
    dest = tmp_path / "paper.pdf"
    upload = _SizedUpload("paper.pdf", MAX_FILE_BYTES + 1, "application/pdf")
    counters = {"total": 0}

    async def _run() -> tuple[Path, int]:
        return await save_upload_streaming(upload, dest, counters=counters, chunk_size=1024 * 1024)

    with pytest.raises(UploadLimitError) as ctx:
        asyncio.run(_run())
    assert ctx.value.status_code == 400
    assert not dest.exists()


def test_save_upload_streaming_unlinks_partial_when_size_unknown(tmp_path: Path) -> None:
    dest = tmp_path / "paper.pdf"

    class _Unseekable:
        filename = "paper.pdf"
        content_type = "application/pdf"

        def __init__(self) -> None:
            self._remaining = MAX_FILE_BYTES + 1
            self.file = self

        def seek(self, *_args: object, **_kwargs: object) -> int:
            raise OSError("not seekable")

        def tell(self) -> int:
            raise OSError("not seekable")

        def read(self, n: int = -1) -> bytes:
            if n is None or n < 0:
                raise AssertionError("full read() is forbidden")
            take = min(int(n), self._remaining)
            self._remaining -= take
            return b"x" * take if take else b""

    counters = {"total": 0}

    async def _run() -> tuple[Path, int]:
        return await save_upload_streaming(
            _Unseekable(),
            dest,
            counters=counters,
            chunk_size=MAX_FILE_BYTES,
        )

    with pytest.raises(UploadLimitError) as ctx:
        asyncio.run(_run())
    assert ctx.value.status_code == 400
    assert not dest.exists()
    assert list(tmp_path.glob("paper*.pdf")) == []


def test_save_upload_streaming_does_not_follow_dangling_symlink(tmp_path: Path) -> None:
    dest = tmp_path / "a.pdf"
    dest.symlink_to(tmp_path / "missing.pdf")
    upload = _Upload("a.pdf", b"new", "application/pdf")
    counters = {"total": 0}

    async def _run() -> tuple[Path, int]:
        return await save_upload_streaming(upload, dest, counters=counters)

    used, written = asyncio.run(_run())
    assert written == 3
    assert used.name == "a_1.pdf"
    assert dest.is_symlink()
    assert used.read_bytes() == b"new"


def test_submit_and_ocr_do_not_full_read_into_memory() -> None:
    submit = Path("services/api/student_submit_service.py").read_text(encoding="utf-8")
    ocr = Path("services/api/assignment_questions_ocr_service.py").read_text(encoding="utf-8")
    forbidden = "write_bytes(await upload_file.read())"
    assert forbidden not in submit
    assert forbidden not in ocr
    assert "write_bytes" not in submit
    assert "write_bytes" not in ocr
