from __future__ import annotations

import io
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

from services.api import upload_text_service as mod
from services.api.upload_text_service import (
    UploadTextDeps,
    ensure_ocr_api_key_aliases,
    extract_text_from_file,
    extract_text_from_image,
    extract_text_from_pdf,
    load_ocr_utils,
    parse_timeout_env,
    save_upload_file,
)


class _Upload:
    def __init__(self, content: bytes):
        self.file = io.BytesIO(content)


class _SeekBroken(io.BytesIO):
    def seek(self, *args, **kwargs):  # type: ignore[override]
        raise OSError("seek broken")


class _UploadSeekBroken:
    def __init__(self, content: bytes):
        self.file = _SeekBroken(content)


def _deps(logs):
    @contextmanager
    def _limit(_sem):
        yield

    return UploadTextDeps(diag_log=lambda event, payload=None: logs.append((event, payload or {})), limit=_limit, ocr_semaphore=object())


@pytest.fixture(autouse=True)
def _reset_ocr_utils(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(mod, "_OCR_UTILS", None)


def test_parse_timeout_env_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OCR_TIMEOUT_SEC", raising=False)
    assert parse_timeout_env("OCR_TIMEOUT_SEC") is None

    monkeypatch.setenv("OCR_TIMEOUT_SEC", "  ")
    assert parse_timeout_env("OCR_TIMEOUT_SEC") is None

    monkeypatch.setenv("OCR_TIMEOUT_SEC", "abc")
    assert parse_timeout_env("OCR_TIMEOUT_SEC") is None


def test_save_upload_file_handles_seek_failure(tmp_path: Path) -> None:
    dest = tmp_path / "out.bin"

    async def _run_in_threadpool(fn):  # type: ignore[no-untyped-def]
        return fn()

    async def _run() -> int:
        return await save_upload_file(
            _UploadSeekBroken(b"abcdef"),  # type: ignore[arg-type]
            dest,
            run_in_threadpool=_run_in_threadpool,
            chunk_size=2,
        )

    import asyncio

    total = asyncio.run(_run())
    assert total == 6
    assert dest.read_bytes() == b"abcdef"


def test_ensure_ocr_aliases_preserve_existing_and_set_silicon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "keep-me")
    monkeypatch.setenv("openai-api-key", "alias-openai")
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.setenv("siliconflow_api_key", " alias-silicon ")

    ensure_ocr_api_key_aliases()

    assert mod.os.getenv("OPENAI_API_KEY") == "keep-me"
    assert mod.os.getenv("SILICONFLOW_API_KEY") == "alias-silicon"


def test_load_ocr_utils_success_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"dotenv": 0}

    fake = types.ModuleType("ocr_utils")

    def _load_env_from_dotenv(_path: Path) -> None:
        called["dotenv"] += 1

    def _ocr_with_sdk(*args, **kwargs):  # type: ignore[no-untyped-def]
        return "ok"

    fake.load_env_from_dotenv = _load_env_from_dotenv  # type: ignore[attr-defined]
    fake.ocr_with_sdk = _ocr_with_sdk  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ocr_utils", fake)

    first = load_ocr_utils()
    second = load_ocr_utils()

    assert first[1] is _ocr_with_sdk
    assert second == first
    assert called["dotenv"] == 1


def test_load_ocr_utils_failure_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "ocr_utils":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)
    out = load_ocr_utils()
    assert out == (None, None)


def test_extract_text_from_pdf_returns_extracted_when_long(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs = []
    deps = _deps(logs)

    class _Page:
        def extract_text(self) -> str:
            return "A " * 30

    class _Pdf:
        pages = [_Page()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    fake_pdfplumber = types.ModuleType("pdfplumber")
    fake_pdfplumber.open = lambda _path: _Pdf()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)
    monkeypatch.setattr(mod, "load_ocr_utils", lambda: (None, None))

    text = extract_text_from_pdf(tmp_path / "a.pdf", deps=deps)
    assert len(text) >= 50
    assert logs[0][0] == "pdf.extract.done"


def test_extract_text_from_pdf_short_text_uses_ocr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs = []
    deps = _deps(logs)

    class _Page:
        def extract_text(self) -> str:
            return "short"

    class _Pdf:
        pages = [_Page()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    fake_pdfplumber = types.ModuleType("pdfplumber")
    fake_pdfplumber.open = lambda _path: _Pdf()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)
    monkeypatch.setattr(mod, "load_ocr_utils", lambda: (None, lambda *args, **kwargs: "ocr " * 30))

    text = extract_text_from_pdf(tmp_path / "a.pdf", deps=deps)
    assert len(text) >= 50
    assert any(event == "pdf.ocr.done" for event, _ in logs)

    # Short non-empty OCR result should still be returned.
    monkeypatch.setattr(mod, "load_ocr_utils", lambda: (None, lambda *args, **kwargs: " short "))
    text2 = extract_text_from_pdf(tmp_path / "a.pdf", deps=deps)
    assert text2 == "short"


def test_extract_text_from_pdf_ocr_error_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs = []
    deps = _deps(logs)

    class _Page:
        def extract_text(self) -> str:
            return "tiny"

    class _Pdf:
        pages = [_Page()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    fake_pdfplumber = types.ModuleType("pdfplumber")
    fake_pdfplumber.open = lambda _path: _Pdf()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)

    # Non-fatal OCR error falls back to extracted text.
    monkeypatch.setattr(
        mod,
        "load_ocr_utils",
        lambda: (None, lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network error"))),
    )
    out = extract_text_from_pdf(tmp_path / "a.pdf", deps=deps)
    assert out == "tiny"
    assert any(event == "pdf.ocr.error" for event, _ in logs)

    # Fatal OCR error should re-raise.
    monkeypatch.setattr(
        mod,
        "load_ocr_utils",
        lambda: (None, lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("OCR unavailable: missing"))),
    )
    with pytest.raises(RuntimeError, match="OCR unavailable"):
        extract_text_from_pdf(tmp_path / "a.pdf", deps=deps)


def test_extract_text_from_pdf_extract_exception_and_empty_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logs = []
    deps = _deps(logs)

    fake_pdfplumber = types.ModuleType("pdfplumber")
    fake_pdfplumber.open = lambda _path: (_ for _ in ()).throw(RuntimeError("bad pdf"))  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)
    monkeypatch.setattr(mod, "load_ocr_utils", lambda: (None, None))

    out = extract_text_from_pdf(tmp_path / "a.pdf", deps=deps)
    assert out == ""
    assert any(event == "pdf.extract.error" for event, _ in logs)


def test_extract_text_from_image_success_and_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs = []
    deps = _deps(logs)

    monkeypatch.setattr(mod, "load_ocr_utils", lambda: (None, lambda *args, **kwargs: "  line1\n\nline2  "))
    out = extract_text_from_image(tmp_path / "a.png", deps=deps)
    assert out == "line1\nline2"
    assert any(event == "image.ocr.done" for event, _ in logs)

    logs.clear()
    monkeypatch.setattr(
        mod,
        "load_ocr_utils",
        lambda: (None, lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ocr boom"))),
    )
    with pytest.raises(RuntimeError, match="ocr boom"):
        extract_text_from_image(tmp_path / "a.png", deps=deps)
    assert any(event == "image.ocr.error" for event, _ in logs)


def test_extract_text_from_file_dispatch_and_read_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs = []
    deps = _deps(logs)

    # pdf and image dispatch
    monkeypatch.setattr(mod, "extract_text_from_pdf", lambda *args, **kwargs: "pdf-text")
    monkeypatch.setattr(mod, "extract_text_from_image", lambda *args, **kwargs: "img-text")

    assert extract_text_from_file(tmp_path / "x.pdf", deps=deps) == "pdf-text"
    assert extract_text_from_file(tmp_path / "x.png", deps=deps) == "img-text"

    # markdown/text path with first read_text failure then fallback read_text success
    txt = tmp_path / "x.txt"
    txt.write_text(" hello ", encoding="utf-8")

    original = Path.read_text

    def _patched_read_text(path: Path, *args, **kwargs):
        if path == txt and kwargs.get("encoding") == "utf-8":
            raise UnicodeError("encoding failed")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _patched_read_text)
    assert extract_text_from_file(txt, deps=deps) == "hello"

    tex = tmp_path / "x.tex"
    tex.write_text("%comment\na\n%ignore\nb\n", encoding="utf-8")
    assert extract_text_from_file(tex, deps=deps) == "a\nb"


def test_extract_text_from_file_unsupported_suffix(tmp_path: Path) -> None:
    deps = _deps([])
    with pytest.raises(RuntimeError, match="不支持的文件类型"):
        extract_text_from_file(tmp_path / "x.doc", deps=deps)
