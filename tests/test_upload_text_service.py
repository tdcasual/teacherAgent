import io
import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.upload_text_service import (
    UploadTextDeps,
    clean_ocr_text,
    ensure_ocr_api_key_aliases,
    extract_text_from_file,
    extract_text_from_image,
    parse_timeout_env,
    save_upload_file,
)


class _Upload:
    def __init__(self, content: bytes):
        self.file = io.BytesIO(content)


class UploadTextServiceTest(unittest.TestCase):
    def test_parse_timeout_env(self):
        os.environ["OCR_TIMEOUT_SEC"] = "3.5"
        self.assertEqual(parse_timeout_env("OCR_TIMEOUT_SEC"), 3.5)
        os.environ["OCR_TIMEOUT_SEC"] = "none"
        self.assertIsNone(parse_timeout_env("OCR_TIMEOUT_SEC"))

    def test_clean_ocr_text(self):
        text = clean_ocr_text("  A \n\n B  \n")
        self.assertEqual(text, "A\nB")

    def test_ensure_ocr_api_key_aliases(self):
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ["openai-api-key"] = "x-key"
        ensure_ocr_api_key_aliases()
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "x-key")

    def test_extract_text_from_file_for_text_and_tex(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            md = root / "a.md"
            tex = root / "b.tex"
            md.write_text(" hello \n\nworld ", encoding="utf-8")
            tex.write_text("%comment\nx=1\n%ignore\ny=2\n", encoding="utf-8")

            @contextmanager
            def _limit(_sem):
                yield

            deps = UploadTextDeps(diag_log=lambda *_args, **_kwargs: None, limit=_limit, ocr_semaphore=object())

            self.assertEqual(extract_text_from_file(md, deps=deps), "hello\nworld")
            self.assertEqual(extract_text_from_file(tex, deps=deps), "x=1\ny=2")

    def test_extract_text_from_image_raises_without_ocr(self):
        from services.api import upload_text_service as mod

        original = mod.load_ocr_utils
        mod.load_ocr_utils = lambda: (None, None)  # type: ignore[assignment]
        try:
            @contextmanager
            def _limit(_sem):
                yield

            deps = UploadTextDeps(diag_log=lambda *_args, **_kwargs: None, limit=_limit, ocr_semaphore=object())
            with self.assertRaises(RuntimeError):
                extract_text_from_image(Path("dummy.png"), deps=deps)
        finally:
            mod.load_ocr_utils = original  # type: ignore[assignment]

    def test_save_upload_file(self):
        with TemporaryDirectory() as td:
            dest = Path(td) / "a.bin"

            async def _run_in_threadpool(fn):  # type: ignore[no-untyped-def]
                return fn()

            async def _run() -> int:
                return await save_upload_file(
                    _Upload(b"abc"),  # type: ignore[arg-type]
                    dest,
                    run_in_threadpool=_run_in_threadpool,
                )

            import asyncio

            total = asyncio.run(_run())
            self.assertEqual(total, 3)
            self.assertEqual(dest.read_bytes(), b"abc")


if __name__ == "__main__":
    unittest.main()
