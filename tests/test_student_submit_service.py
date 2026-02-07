import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_submit_service import StudentSubmitDeps, submit


@dataclass
class _Upload:
    filename: str
    content: bytes

    async def read(self) -> bytes:
        return self.content


class StudentSubmitServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_submit_without_assignment_sets_auto_assignment(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {}

            def _run_script(args):
                captured["args"] = list(args)
                return "ok"

            deps = StudentSubmitDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                student_submissions_dir=root / "submissions",
                run_script=_run_script,
            )

            result = await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id=None,
                auto_assignment=False,
                deps=deps,
            )

            self.assertEqual(result.get("ok"), True)
            args = captured["args"]
            self.assertIn("--auto-assignment", args)
            self.assertNotIn("--assignment-id", args)

    async def test_submit_with_assignment_keeps_assignment_flag(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {}

            def _run_script(args):
                captured["args"] = list(args)
                return "ok"

            deps = StudentSubmitDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                student_submissions_dir=root / "submissions",
                run_script=_run_script,
            )

            await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )

            args = captured["args"]
            self.assertIn("--assignment-id", args)
            self.assertIn("HW_1", args)
            self.assertNotIn("--auto-assignment", args)


if __name__ == "__main__":
    unittest.main()
