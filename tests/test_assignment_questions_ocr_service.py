import io
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from services.api.assignment_questions_ocr_service import (
    AssignmentQuestionsOcrDeps,
    assignment_questions_ocr,
)
from services.api.upload_limits import MAX_FILE_BYTES, MAX_FILES


@dataclass
class _Upload:
    filename: str
    content: bytes
    content_type: str = "image/png"
    file: io.BytesIO = field(init=False)

    def __post_init__(self) -> None:
        self.file = io.BytesIO(self.content)

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            raise AssertionError("full read() is forbidden")
        return self.file.read(size)


class AssignmentQuestionsOcrServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_writes_files_and_runs_script(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {}

            def _run_script(args):
                captured["args"] = list(args)
                return "ok"

            deps = AssignmentQuestionsOcrDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                run_script=_run_script,
            )

            result = await assignment_questions_ocr(
                assignment_id="HW_1",
                files=[_Upload(filename="q1.png", content=b"abc")],
                kp_id="kp1",
                difficulty="hard",
                tags="ocr,math",
                ocr_mode="FREE_OCR",
                language="zh",
                deps=deps,
            )

            self.assertEqual(result.get("ok"), True)
            self.assertEqual(len(result.get("files") or []), 1)
            file_path = Path(result["files"][0])
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_bytes(), b"abc")
            args = captured["args"]
            self.assertIn("--assignment-id", args)
            self.assertIn("HW_1", args)
            self.assertIn("--files", args)

    async def test_assignment_id_is_sanitized_and_kept_under_ocr_root(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {}

            def _run_script(args):
                captured["args"] = list(args)
                return "ok"

            deps = AssignmentQuestionsOcrDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                run_script=_run_script,
            )

            result = await assignment_questions_ocr(
                assignment_id="../../../../outside",
                files=[_Upload(filename="q1.png", content=b"abc")],
                kp_id="kp1",
                difficulty="hard",
                tags="ocr,math",
                ocr_mode="FREE_OCR",
                language="zh",
                deps=deps,
            )

            self.assertEqual(result.get("assignment_id"), "outside")
            file_path = Path((result.get("files") or [""])[0]).resolve()
            ocr_root = (root / "uploads" / "assignment_ocr").resolve()
            self.assertIn(ocr_root, file_path.parents)
            args = captured["args"]
            aid_index = args.index("--assignment-id") + 1
            self.assertEqual(args[aid_index], "outside")

    def _deps(self, root: Path, captured: dict | None = None) -> AssignmentQuestionsOcrDeps:
        def _run_script(args):
            if captured is not None:
                captured["args"] = list(args)
            return "ok"

        return AssignmentQuestionsOcrDeps(
            uploads_dir=root / "uploads",
            app_root=root / "repo",
            run_script=_run_script,
        )

    async def test_ocr_rejects_21st_file(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            files = [_Upload(filename=f"q{i}.png", content=b"x") for i in range(MAX_FILES + 1)]
            with self.assertRaises(HTTPException) as ctx:
                await assignment_questions_ocr(
                    assignment_id="HW_1",
                    files=files,
                    kp_id="kp1",
                    difficulty="hard",
                    tags="ocr",
                    ocr_mode="FREE_OCR",
                    language="zh",
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_ocr_rejects_file_over_20mb(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))

            class _File:
                def tell(self) -> int:
                    return getattr(self, "_pos", 0)

                def seek(self, offset: int, whence: int = 0) -> int:
                    if whence == 2:
                        self._pos = MAX_FILE_BYTES + 1
                    else:
                        self._pos = int(offset)
                    return self._pos

                def read(self, n: int = -1) -> bytes:
                    return b""

            class _Sized:
                filename = "q1.png"
                content_type = "image/png"
                file = _File()

                async def read(self, size: int = -1) -> bytes:
                    if size is None or size < 0:
                        raise AssertionError("full read() is forbidden")
                    return self.file.read(size)

            with self.assertRaises(HTTPException) as ctx:
                await assignment_questions_ocr(
                    assignment_id="HW_1",
                    files=[_Sized()],
                    kp_id="kp1",
                    difficulty="hard",
                    tags="ocr",
                    ocr_mode="FREE_OCR",
                    language="zh",
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_ocr_rejects_mime_mismatch(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            with self.assertRaises(HTTPException) as ctx:
                await assignment_questions_ocr(
                    assignment_id="HW_1",
                    files=[_Upload(filename="q1.png", content=b"abc", content_type="application/pdf")],
                    kp_id="kp1",
                    difficulty="hard",
                    tags="ocr",
                    ocr_mode="FREE_OCR",
                    language="zh",
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_ocr_accepts_bmp_and_tex(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            result = await assignment_questions_ocr(
                assignment_id="HW_1",
                files=[
                    _Upload(filename="q1.bmp", content=b"bmp", content_type="image/bmp"),
                    _Upload(filename="q2.tex", content=b"x=1", content_type="application/x-tex"),
                ],
                kp_id="kp1",
                difficulty="hard",
                tags="ocr",
                ocr_mode="FREE_OCR",
                language="zh",
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(len(result.get("files") or []), 2)

    async def test_ocr_collision_renames_without_overwrite(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            ocr_dir = (root / "uploads" / "assignment_ocr" / "HW_1")
            ocr_dir.mkdir(parents=True, exist_ok=True)
            original = ocr_dir / "q1.png"
            original.write_bytes(b"original")
            result = await assignment_questions_ocr(
                assignment_id="HW_1",
                files=[_Upload(filename="q1.png", content=b"new")],
                kp_id="kp1",
                difficulty="hard",
                tags="ocr",
                ocr_mode="FREE_OCR",
                language="zh",
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(original.read_bytes(), b"original")
            saved = [Path(p) for p in (result.get("files") or [])]
            self.assertEqual(len(saved), 1)
            self.assertNotEqual(saved[0].resolve(), original.resolve())
            self.assertEqual(saved[0].read_bytes(), b"new")


if __name__ == "__main__":
    unittest.main()
