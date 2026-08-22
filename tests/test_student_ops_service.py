import asyncio
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from services.api.student_ops_service import (
    StudentOpsDeps,
    update_profile,
    upload_files,
    verify_student,
)
from services.api.upload_limits import MAX_FILE_BYTES, MAX_FILES

_STUDENT_MIME = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".md": "text/markdown",
    ".csv": "text/csv",
}


class _Upload:
    def __init__(self, name: str, data: bytes, content_type: str | None = None):
        self.filename = name
        self.file = io.BytesIO(data)
        suffix = Path(name).suffix.lower()
        self.content_type = (
            _STUDENT_MIME.get(suffix, "application/octet-stream") if content_type is None else content_type
        )

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            raise AssertionError("full read() is forbidden")
        return self.file.read(size)


class StudentOpsServiceTest(unittest.TestCase):
    def test_verify_student_missing_and_multiple(self):
        logs = []
        deps = StudentOpsDeps(
            uploads_dir=Path("/tmp"),
            app_root=Path("/tmp/app"),
            sanitize_filename=lambda s: s,
            run_script=lambda _args: "",
            student_candidates_by_name=lambda _name: [{"student_id": "S1", "class_name": "高二2401班"}, {"student_id": "S2", "class_name": "高二2402班"}],
            normalize=lambda s: "".join(str(s).split()).lower(),
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        )
        missing = verify_student("", "", deps=deps)
        self.assertEqual(missing.get("error"), "missing_name")

        multiple = verify_student("张三", "", deps=deps)
        self.assertEqual(multiple.get("error"), "multiple")
        self.assertEqual(logs[-1][0], "student.verify.multiple")

    def test_update_profile_builds_script_args(self):
        captured = {}
        deps = StudentOpsDeps(
            uploads_dir=Path("/tmp"),
            app_root=Path("/tmp/app"),
            sanitize_filename=lambda s: s,
            run_script=lambda args: captured.setdefault("args", list(args)) or "ok",
            student_candidates_by_name=lambda _name: [],
            normalize=lambda s: str(s),
            diag_log=lambda _e, _p=None: None,
        )
        payload = update_profile(
            student_id="S1",
            weak_kp="力学",
            strong_kp="电学",
            medium_kp="热学",
            next_focus="受力分析",
            interaction_note="课堂表现不错",
            deps=deps,
        )
        args = captured.get("args") or []
        self.assertIn("--student-id", args)
        self.assertIn("S1", args)
        self.assertTrue(payload.get("ok"))

    def test_upload_files_saves_sanitized_names(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = StudentOpsDeps(
                uploads_dir=root,
                app_root=Path(td),
                sanitize_filename=lambda s: "" if s.startswith(".") else s,
                run_script=lambda _args: "",
                student_candidates_by_name=lambda _name: [],
                normalize=lambda s: str(s),
                diag_log=lambda _e, _p=None: None,
            )

            async def _run():
                return await upload_files(
                    [_Upload("a.txt", b"1"), _Upload(".DS_Store", b"x"), _Upload("b.txt", b"2")],
                    deps=deps,
                )

            out = asyncio.run(_run())
            self.assertEqual(len(out.get("saved") or []), 2)


class StudentOpsUploadLimitsTest(unittest.IsolatedAsyncioTestCase):
    def _deps(self, root: Path) -> StudentOpsDeps:
        return StudentOpsDeps(
            uploads_dir=root,
            app_root=root,
            sanitize_filename=lambda s: "" if str(s).startswith(".") else Path(str(s)).name,
            run_script=lambda _args: "",
            student_candidates_by_name=lambda _name: [],
            normalize=lambda s: str(s),
            diag_log=lambda _e, _p=None: None,
        )

    async def test_upload_rejects_21st_file(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            files = [_Upload(f"f{i}.txt", b"x") for i in range(MAX_FILES + 1)]
            with self.assertRaises(HTTPException) as ctx:
                await upload_files(files, deps=deps)
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_upload_rejects_file_over_20mb(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))

            class _Sized:
                filename = "big.pdf"
                content_type = "application/pdf"

                def __init__(self) -> None:
                    self.file = io.BytesIO(b"x")
                    self._size = MAX_FILE_BYTES + 1

                def tell(self) -> int:  # pragma: no cover - unused if file is nested
                    return 0

            sized = _Sized()

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

            sized.file = _File()
            with self.assertRaises(HTTPException) as ctx:
                await upload_files([sized], deps=deps)
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_upload_rejects_mime_mismatch(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            with self.assertRaises(HTTPException) as ctx:
                await upload_files(
                    [_Upload("homework.pdf", b"%PDF", content_type="image/jpeg")],
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_upload_collision_renames_without_overwrite(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            existing = root / "a.txt"
            existing.write_bytes(b"original")
            deps = self._deps(root)
            out = await upload_files([_Upload("a.txt", b"new")], deps=deps)
            saved = [Path(p) for p in (out.get("saved") or [])]
            self.assertEqual(len(saved), 1)
            self.assertNotEqual(saved[0], existing)
            self.assertEqual(existing.read_bytes(), b"original")
            self.assertEqual(saved[0].read_bytes(), b"new")

    async def test_upload_allows_empty_mime_for_allowed_suffix(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            out = await upload_files(
                [_Upload("notes.md", b"# hi", content_type="")],
                deps=deps,
            )
            self.assertEqual(len(out.get("saved") or []), 1)


if __name__ == "__main__":
    unittest.main()
