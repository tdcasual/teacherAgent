from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest
from fastapi import HTTPException

from services.api.assignment_questions_ocr_service import (
    OCR_ALLOWED_SUFFIXES,
    AssignmentQuestionsOcrDeps,
    assignment_questions_ocr,
)
from services.api.assignment_upload_start_service import _ASSIGNMENT_ALLOWED_SUFFIXES
from services.api.student_ops_service import (
    STUDENT_ALLOWED_SUFFIXES,
    StudentOpsDeps,
    unique_upload_dest,
    upload_files,
)
from services.api.student_submit_service import STUDENT_ALLOWED_SUFFIXES as SUBMIT_SUFFIXES
from services.api.student_submit_service import StudentSubmitDeps, submit
from services.api.upload_limits import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES


class _Upload:
    def __init__(self, filename: str, payload: bytes, content_type: str = ""):
        self.filename = filename
        self.content = payload
        self.content_type = content_type
        self.file = io.BytesIO(payload)

    async def read(self, size: int = -1) -> bytes:
        if size is None or int(size) < 0:
            raise AssertionError("full read() is forbidden")
        return self.file.read(int(size))


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
    def __init__(self, filename: str, size: int, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self.file = _SizedFile(size)

    async def read(self, size: int = -1) -> bytes:
        if size is None or int(size) < 0:
            raise AssertionError("full read() is forbidden")
        return self.file.read(int(size))


async def _save_upload_file(upload: object, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = getattr(upload, "content", None)
    if payload is None:
        file_obj = getattr(upload, "file", None)
        if file_obj is not None:
            try:
                file_obj.seek(0)
            except (OSError, ValueError, TypeError):
                pass
            payload = file_obj.read()
        else:
            payload = getattr(upload, "payload", b"")
    dest.write_bytes(payload)
    return len(payload)


def _ops_deps(root: Path) -> StudentOpsDeps:
    return StudentOpsDeps(
        uploads_dir=root / "uploads",
        app_root=root / "app",
        sanitize_filename=lambda name: Path(str(name or "")).name,
        save_upload_file=_save_upload_file,
        run_script=lambda _args: "",
        student_candidates_by_name=lambda _name: [],
        normalize=lambda value: str(value),
        diag_log=lambda _event, _payload=None: None,
        issue_student_candidate_id=lambda sid: f"cid_{sid}",
    )


def _submit_deps(root: Path) -> StudentSubmitDeps:
    return StudentSubmitDeps(
        uploads_dir=root / "uploads",
        app_root=root / "repo",
        student_submissions_dir=root / "submissions",
        run_script=lambda _args: "ok",
        compute_assignment_progress=lambda _assignment_id, _include_students: {"ok": False},
        student_memory_auto_propose_from_assignment_evidence=lambda **_kwargs: {
            "ok": False,
            "created": False,
        },
        load_assignment_teacher_id=lambda _assignment_id: None,
        diag_log=lambda _event, _payload: None,
        save_upload_file=_save_upload_file,
    )


def _ocr_deps(root: Path) -> AssignmentQuestionsOcrDeps:
    return AssignmentQuestionsOcrDeps(
        uploads_dir=root / "uploads",
        app_root=root / "repo",
        run_script=lambda _args: "ok",
        save_upload_file=_save_upload_file,
    )



def _error_code(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("error") or "")
    return str(detail)


def test_shared_numeric_caps() -> None:
    assert MAX_FILES == 20
    assert MAX_FILE_BYTES == 20 * 1024 * 1024
    assert MAX_TOTAL_BYTES == 80 * 1024 * 1024


def test_upload_limits_module_is_numbers_only() -> None:
    source = Path("services/api/upload_limits.py").read_text(encoding="utf-8")
    assert "save_upload_streaming" not in source
    assert "save_limited_uploads" not in source
    assert "mime" not in source.lower()
    assert "MAX_FILES" in source
    assert "MAX_FILE_BYTES" in source
    assert "MAX_TOTAL_BYTES" in source


def test_assignment_import_shared_numeric_caps() -> None:
    from services.api import assignment_upload_start_service as assignment
    from services.api import upload_limits as limits

    assert assignment.MAX_FILES_PER_UPLOAD_FIELD is limits.MAX_FILES
    assert assignment.MAX_UPLOAD_FILE_SIZE_BYTES is limits.MAX_FILE_BYTES
    assert assignment.MAX_UPLOAD_TOTAL_SIZE_BYTES is limits.MAX_TOTAL_BYTES


def test_assignment_keep_wide_suffix_sets() -> None:
    assert {".bmp", ".tex", ".markdown"} <= _ASSIGNMENT_ALLOWED_SUFFIXES
    assert OCR_ALLOWED_SUFFIXES == _ASSIGNMENT_ALLOWED_SUFFIXES


def test_student_submit_reuses_student_suffix_set() -> None:
    assert SUBMIT_SUFFIXES is STUDENT_ALLOWED_SUFFIXES
    assert {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md", ".csv"} <= STUDENT_ALLOWED_SUFFIXES
    assert ".xlsx" not in STUDENT_ALLOWED_SUFFIXES
    assert ".exe" not in STUDENT_ALLOWED_SUFFIXES


def test_submit_and_ocr_do_not_full_read() -> None:
    submit_src = Path("services/api/student_submit_service.py").read_text(encoding="utf-8")
    ocr_src = Path("services/api/assignment_questions_ocr_service.py").read_text(encoding="utf-8")
    ops_src = Path("services/api/student_ops_service.py").read_text(encoding="utf-8")
    assert "await upload_file.read()" not in submit_src
    assert "await upload_file.read()" not in ocr_src
    assert "write_bytes" not in submit_src
    assert "write_bytes" not in ocr_src
    assert "save_upload_file" in submit_src
    assert "save_upload_file" in ocr_src
    assert "save_upload_file" in ops_src
    assert "content_type" not in ops_src


def test_upload_route_requires_principal() -> None:
    text = Path("services/api/routes/misc_general_routes.py").read_text(encoding="utf-8")
    assert "require_principal(" in text


def test_upload_rejects_21st_file(tmp_path: Path) -> None:
    files = [_Upload(f"n{i}.pdf", b"x") for i in range(MAX_FILES + 1)]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(upload_files(files, deps=_ops_deps(tmp_path)))
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "too_many_files"


def test_submit_rejects_21st_file(tmp_path: Path) -> None:
    files = [_Upload(f"n{i}.pdf", b"x") for i in range(MAX_FILES + 1)]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            submit(
                student_id="S1",
                files=files,
                assignment_id="HW_1",
                auto_assignment=False,
                deps=_submit_deps(tmp_path),
            )
        )
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "too_many_files"


def test_ocr_rejects_21st_file(tmp_path: Path) -> None:
    files = [_Upload(f"n{i}.png", b"x") for i in range(MAX_FILES + 1)]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            assignment_questions_ocr(
                assignment_id="HW_1",
                files=files,
                kp_id=None,
                difficulty=None,
                tags=None,
                ocr_mode=None,
                language=None,
                deps=_ocr_deps(tmp_path),
            )
        )
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "too_many_files"


def test_upload_rejects_over_max_file_bytes(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_files(
                [_SizedUpload("paper.pdf", MAX_FILE_BYTES + 1)],
                deps=_ops_deps(tmp_path),
            )
        )
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "file_too_large"


def test_submit_rejects_over_max_file_bytes(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            submit(
                student_id="S1",
                files=[_SizedUpload("paper.pdf", MAX_FILE_BYTES + 1)],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=_submit_deps(tmp_path),
            )
        )
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "file_too_large"


def test_ocr_rejects_over_max_file_bytes(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            assignment_questions_ocr(
                assignment_id="HW_1",
                files=[_SizedUpload("paper.png", MAX_FILE_BYTES + 1, content_type="image/png")],
                kp_id=None,
                difficulty=None,
                tags=None,
                ocr_mode=None,
                language=None,
                deps=_ocr_deps(tmp_path),
            )
        )
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "file_too_large"


def test_legal_suffix_not_rejected_for_empty_or_octet_stream_mime(tmp_path: Path) -> None:
    deps = _ops_deps(tmp_path)
    empty = asyncio.run(upload_files([_Upload("notes.pdf", b"%PDF", "")], deps=deps))
    octet = asyncio.run(
        upload_files(
            [_Upload("sheet.csv", b"a,b\n", "application/octet-stream")],
            deps=deps,
        )
    )
    excel_lie = asyncio.run(
        upload_files(
            [_Upload("scores.csv", b"a,b\n", "application/vnd.ms-excel")],
            deps=deps,
        )
    )
    assert len(empty["saved"]) == 1
    assert len(octet["saved"]) == 1
    assert len(excel_lie["saved"]) == 1


def test_unknown_suffix_rejected_even_with_pdf_mime(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_files(
                [_Upload("malware.exe", b"MZ", "application/pdf")],
                deps=_ops_deps(tmp_path),
            )
        )
    assert exc.value.status_code == 400
    assert _error_code(exc.value) == "invalid_suffix"
    assert "不支持的文件类型" in str(exc.value.detail)


def test_submit_does_not_overwrite_same_name(tmp_path: Path) -> None:
    deps = _submit_deps(tmp_path)
    first = tmp_path / "uploads"
    first.mkdir(parents=True, exist_ok=True)
    (first / "a.pdf").write_bytes(b"old")
    result = asyncio.run(
        submit(
            student_id="S1",
            files=[_Upload("a.pdf", b"new")],
            assignment_id="HW_1",
            auto_assignment=False,
            deps=deps,
        )
    )
    assert result.get("ok") is True
    assert (first / "a.pdf").read_bytes() == b"old"
    renamed = list(first.glob("a-*.pdf")) + list(first.glob("a-2.pdf"))
    assert any(path.read_bytes() == b"new" for path in renamed)


def test_ocr_accepts_tex_and_bmp(tmp_path: Path) -> None:
    result = asyncio.run(
        assignment_questions_ocr(
            assignment_id="HW_1",
            files=[
                _Upload("q1.tex", b"x=1", "application/octet-stream"),
                _Upload("q2.bmp", b"BM", "image/bmp"),
            ],
            kp_id=None,
            difficulty=None,
            tags=None,
            ocr_mode=None,
            language=None,
            deps=_ocr_deps(tmp_path),
        )
    )
    assert result.get("ok") is True
    assert len(result.get("files") or []) == 2




def test_unique_upload_dest_skips_existing_and_symlink(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_bytes(b"old")
    (tmp_path / "ghost").symlink_to(tmp_path / "missing-target")
    dest = unique_upload_dest(tmp_path, "a.pdf")
    assert dest.name != "a.pdf"
    assert dest.parent == tmp_path
    assert dest.exists()
    skipped = unique_upload_dest(tmp_path, "ghost")
    assert skipped.name != "ghost"



def test_http_upload_exe_with_pdf_mime_is_invalid_suffix(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from tests.helpers.app_factory import create_test_app

    app_mod = create_test_app(tmp_path)
    with TestClient(app_mod.app) as client:
        res = client.post(
            "/upload",
            files=[("files", ("malware.exe", b"MZ", "application/pdf"))],
        )
    assert res.status_code == 400
    detail = res.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error") == "invalid_suffix"


def test_http_upload_pdf_with_octet_stream_is_200(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from tests.helpers.app_factory import create_test_app

    app_mod = create_test_app(tmp_path)
    with TestClient(app_mod.app) as client:
        res = client.post(
            "/upload",
            files=[("files", ("notes.pdf", b"%PDF-1.4 notes", "application/octet-stream"))],
        )
    assert res.status_code == 200
    payload = res.json()
    assert len(payload.get("saved") or []) == 1


def test_http_upload_requires_bearer_when_auth_required(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from tests.helpers.app_factory import create_test_app

    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "upload-cap-secret")
    monkeypatch.setenv("MASTER_KEY_DEV_DEFAULT", "dev-key")
    app_mod = create_test_app(
        tmp_path,
        env_overrides={
            "AUTH_REQUIRED": "1",
            "AUTH_TOKEN_SECRET": "upload-cap-secret",
            "MASTER_KEY_DEV_DEFAULT": "dev-key",
        },
        use_runtime_entrypoint=True,
        reload_module=True,
    )
    with TestClient(app_mod.app) as client:
        res = client.post(
            "/upload",
            files=[("files", ("notes.pdf", b"%PDF-1.4 notes", "application/pdf"))],
        )
    assert res.status_code == 401
    assert res.json().get("detail") == "missing_authorization"
