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


def _deps(root: Path, **overrides) -> StudentSubmitDeps:
    fields = dict(
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
    fields.update(overrides)
    return StudentSubmitDeps(**fields)


def _progress(*, submitted: bool, score: float = 0.0, attempt_id: str = "submission_1") -> dict:
    return {
        "ok": True,
        "students": [
            {
                "student_id": "S1",
                "evidence": {
                    "schema": "assignment_progress_evidence/v1",
                    "signals": {
                        "submitted": submitted,
                        "best_graded_total": 10 if submitted else 0,
                        "best_score_earned": score,
                        "best_attempt_id": attempt_id,
                        "min_graded_total": 1,
                    },
                },
            }
        ],
    }


class StudentSubmitServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_submit_requires_assignment_id(self):
        with TemporaryDirectory() as td:
            captured = {}
            deps = _deps(Path(td), run_script=lambda args: captured.setdefault("args", list(args)) or "ok")
            with self.assertRaises(StudentSubmitError) as ctx:
                await submit(
                    student_id="S1",
                    files=[_Upload(filename="a1.pdf", content=b"1")],
                    assignment_id=None,
                    auto_assignment=False,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "assignment_id_required")
            self.assertNotIn("args", captured)

    async def test_submit_rejects_auto_assignment_true(self):
        with TemporaryDirectory() as td:
            captured = {}
            deps = _deps(Path(td), run_script=lambda args: captured.setdefault("args", list(args)) or "ok")
            with self.assertRaises(StudentSubmitError) as ctx:
                await submit(
                    student_id="S1",
                    files=[_Upload(filename="a1.pdf", content=b"1")],
                    assignment_id="HW_1",
                    auto_assignment=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "auto_assignment_disabled")
            self.assertNotIn("args", captured)

    async def test_submit_with_assignment_keeps_assignment_flag(self):
        with TemporaryDirectory() as td:
            captured = {}
            deps = _deps(
                Path(td),
                run_script=lambda args: captured.setdefault("args", list(args)) or "ok",
                compute_assignment_progress=lambda _assignment_id, _include_students: _progress(
                    submitted=True, score=8.0, attempt_id="submission_ok"
                ),
            )

            result = await submit(
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
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("submitted"))
            self.assertEqual(result.get("assignment_id"), "HW_1")
            self.assertEqual(result.get("attempt_id"), "submission_ok")
            self.assertEqual(result.get("official_score"), 8.0)

    async def test_submit_returns_200_payload_when_min_graded_total_fails(self):
        with TemporaryDirectory() as td:
            deps = _deps(
                Path(td),
                compute_assignment_progress=lambda _assignment_id, _include_students: _progress(
                    submitted=False, score=0.0, attempt_id="submission_empty"
                ),
            )
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="blank.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertFalse(result.get("submitted"))
            self.assertEqual(result.get("assignment_id"), "HW_1")
            self.assertEqual(result.get("reason"), "min_graded_total")
            self.assertIsNone(result.get("official_score"))

    async def test_submit_uses_progress_unavailable_when_progress_read_fails(self):
        with TemporaryDirectory() as td:
            def _boom(_assignment_id, _include_students):
                raise RuntimeError("progress down")

            deps = _deps(Path(td), compute_assignment_progress=_boom)
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertFalse(result.get("submitted"))
            self.assertEqual(result.get("reason"), "progress_unavailable")
            self.assertIsNone(result.get("official_score"))

    async def test_submit_uses_progress_unavailable_when_progress_not_ok(self):
        with TemporaryDirectory() as td:
            deps = _deps(
                Path(td),
                compute_assignment_progress=lambda _assignment_id, _include_students: {"ok": False},
            )
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertFalse(result.get("submitted"))
            self.assertEqual(result.get("reason"), "progress_unavailable")

    async def test_submit_rejects_invalid_student_id(self):
        with TemporaryDirectory() as td:
            deps = _deps(Path(td))

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
            deps = _deps(Path(td))

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

            deps = _deps(
                root,
                run_script=_run_script,
                compute_assignment_progress=_compute_assignment_progress,
                student_memory_auto_propose_from_assignment_evidence=_auto_propose,
                load_assignment_teacher_id=lambda assignment_id: (
                    "t_zhang" if assignment_id == "HW_1" else None
                ),
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
            self.assertEqual(auto_kwargs.get("teacher_id"), "t_zhang")
            self.assertEqual(auto_kwargs.get("student_id"), "S1")
            self.assertEqual(auto_kwargs.get("assignment_id"), "HW_1")
            self.assertIsInstance(auto_kwargs.get("evidence"), dict)

    async def test_submit_skips_memory_when_assignment_has_no_teacher_id(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            captured = {"auto": 0}

            def _auto_propose(**kwargs):
                captured["auto"] += 1
                captured["auto_kwargs"] = dict(kwargs)
                return {"ok": True, "created": True, "proposal_id": "smem_1"}

            deps = _deps(
                root,
                compute_assignment_progress=lambda _assignment_id, _include_students: _progress(submitted=True, score=3),
                student_memory_auto_propose_from_assignment_evidence=_auto_propose,
            )

            result = await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(captured["auto"], 0)


class StudentSubmitServiceImportGuardTest(unittest.TestCase):
    def test_student_submit_service_does_not_import_fastapi(self):
        from pathlib import Path

        source = Path("services/api/student_submit_service.py").read_text(encoding="utf-8")
        self.assertNotIn("from fastapi", source)
        self.assertNotIn("import fastapi", source)


if __name__ == "__main__":
    unittest.main()
