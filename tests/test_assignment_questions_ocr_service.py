import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_questions_ocr_service import (
    AssignmentQuestionsOcrDeps,
    assignment_questions_ocr,
)


@dataclass
class _Upload:
    filename: str
    content: bytes

    async def read(self) -> bytes:
        return self.content


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


if __name__ == "__main__":
    unittest.main()
