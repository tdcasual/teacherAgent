import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_submit_service import StudentSubmitDeps, StudentSubmitError, submit


async def _save_upload_file(upload, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = getattr(upload, "content", b"")
    dest.write_bytes(payload)
    return len(payload)


@dataclass
class _Upload:
    filename: str
    content: bytes

    async def read(self, size: int = -1) -> bytes:
        if size is None or int(size) < 0:
            raise AssertionError("full read() is forbidden")
        return self.content[: int(size)] if int(size) else b""


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
                compute_assignment_progress=lambda _assignment_id, _include_students: {"ok": False},
                student_memory_auto_propose_from_assignment_evidence=lambda **_kwargs: {
                    "ok": False,
                    "created": False,
                },
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                diag_log=lambda _event, _payload: None,
                save_upload_file=_save_upload_file,
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
                compute_assignment_progress=lambda _assignment_id, _include_students: {"ok": False},
                student_memory_auto_propose_from_assignment_evidence=lambda **_kwargs: {
                    "ok": False,
                    "created": False,
                },
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                diag_log=lambda _event, _payload: None,
                save_upload_file=_save_upload_file,
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

    async def test_submit_rejects_invalid_student_id(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = StudentSubmitDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                student_submissions_dir=root / "submissions",
                run_script=lambda _args: "ok",
                compute_assignment_progress=lambda _assignment_id, _include_students: {"ok": False},
                student_memory_auto_propose_from_assignment_evidence=lambda **_kwargs: {
                    "ok": False,
                    "created": False,
                },
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                diag_log=lambda _event, _payload: None,
                save_upload_file=_save_upload_file,
            )

            with self.assertRaises(StudentSubmitError) as ctx:
                await submit(
                    student_id="../escape",
                    files=[_Upload(filename="a1.pdf", content=b"1")],
                    assignment_id="HW_1",
                    auto_assignment=False,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "invalid_student_id")

    async def test_submit_rejects_invalid_assignment_id(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = StudentSubmitDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                student_submissions_dir=root / "submissions",
                run_script=lambda _args: "ok",
                compute_assignment_progress=lambda _assignment_id, _include_students: {"ok": False},
                student_memory_auto_propose_from_assignment_evidence=lambda **_kwargs: {
                    "ok": False,
                    "created": False,
                },
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                diag_log=lambda _event, _payload: None,
                save_upload_file=_save_upload_file,
            )

            with self.assertRaises(StudentSubmitError) as ctx:
                await submit(
                    student_id="S1",
                    files=[_Upload(filename="a1.pdf", content=b"1")],
                    assignment_id="../escape",
                    auto_assignment=False,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "invalid_assignment_id")

    async def test_submit_with_assignment_runs_assignment_evidence_auto_propose(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {}

            def _run_script(args):
                captured["args"] = list(args)
                return "ok"

            def _compute_assignment_progress(assignment_id, include_students):
                captured["progress_call"] = (assignment_id, include_students)
                return {
                    "ok": True,
                    "students": [
                        {
                            "student_id": "S1",
                            "evidence": {
                                "schema": "assignment_progress_evidence/v1",
                                "signals": {
                                    "submitted": True,
                                    "best_graded_total": 10,
                                    "best_score_earned": 3,
                                },
                            },
                        }
                    ],
                }

            def _auto_propose(**kwargs):
                captured["auto_kwargs"] = dict(kwargs)
                return {"ok": True, "created": True, "proposal_id": "smem_1"}

            deps = StudentSubmitDeps(
                uploads_dir=root / "uploads",
                app_root=root / "repo",
                student_submissions_dir=root / "submissions",
                run_script=_run_script,
                compute_assignment_progress=_compute_assignment_progress,
                student_memory_auto_propose_from_assignment_evidence=_auto_propose,
                resolve_teacher_id=lambda value: str(value or "teacher-default"),
                diag_log=lambda _event, _payload: None,
                save_upload_file=_save_upload_file,
            )

            result = await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )

            self.assertTrue(result.get("ok"))
            self.assertEqual(captured.get("progress_call"), ("HW_1", True))
            auto_kwargs = captured.get("auto_kwargs") or {}
            self.assertEqual(auto_kwargs.get("teacher_id"), "teacher-default")
            self.assertEqual(auto_kwargs.get("student_id"), "S1")
            self.assertEqual(auto_kwargs.get("assignment_id"), "HW_1")
            self.assertIsInstance(auto_kwargs.get("evidence"), dict)


class StudentSubmitServiceImportGuardTest(unittest.TestCase):
    def test_student_submit_service_does_not_import_fastapi(self):
        from pathlib import Path

        source = Path("services/api/student_submit_service.py").read_text(encoding="utf-8")
        self.assertNotIn("from fastapi", source)
        self.assertNotIn("import fastapi", source)


if __name__ == "__main__":
    unittest.main()
