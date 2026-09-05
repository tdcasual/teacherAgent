import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from services.api.assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    best_submission_attempt,
    compute_submission_attempt,
    counted_grade_item,
    list_submission_attempts,
)
from services.api.student_submit_service import (
    StudentSubmitDeps,
    StudentSubmitError,
    authorize_student_submit_assignment,
    submit,
)


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


def _attempt_deps(root: Path) -> AssignmentSubmissionAttemptDeps:
    return AssignmentSubmissionAttemptDeps(
        student_submissions_dir=root / "submissions",
        grade_count_conf_threshold=0.6,
    )


def _progress_from_disk(root: Path, assignment_id: str, _include_students: bool) -> dict:
    deps = _attempt_deps(root)
    attempts = list_submission_attempts(assignment_id, "S1", deps=deps)
    best = best_submission_attempt(attempts)
    submitted = bool(best)
    return {
        "ok": True,
        "students": [
            {
                "student_id": "S1",
                "evidence": {
                    "schema": "assignment_progress_evidence/v1",
                    "signals": {
                        "submitted": submitted,
                        "best_graded_total": int((best or {}).get("graded_total") or 0),
                        "best_score_earned": (best or {}).get("score_earned"),
                        "best_attempt_id": str((best or {}).get("attempt_id") or ""),
                        "min_graded_total": 1,
                    },
                },
            }
        ],
    }


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
    async def test_submit_rejects_unpublished_assignment(self):
        with TemporaryDirectory() as td:
            captured = {}

            def _deny(assignment_id: str, student_id: str) -> None:
                raise StudentSubmitError(403, "forbidden_assignment_scope")

            deps = _deps(
                Path(td),
                run_script=lambda args: captured.setdefault("args", list(args)) or "ok",
                authorize_student_submit=_deny,
            )
            with self.assertRaises(StudentSubmitError) as ctx:
                await submit(
                    student_id="S1",
                    files=[_Upload(filename="a1.pdf", content=b"1")],
                    assignment_id="HW_DRAFT",
                    auto_assignment=False,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertNotIn("args", captured)

    def test_authorize_student_submit_requires_published_roster_and_enrollment(self):
        def _load_meta(assignment_id: str):
            if assignment_id == "missing":
                return None
            if assignment_id == "draft":
                return {
                    "teacher_id": "t1",
                    "subject_id": "physics",
                    "visibility_status": "draft",
                    "expected_students": ["S1"],
                }
            return {
                "teacher_id": "t1",
                "subject_id": "physics",
                "visibility_status": "published",
                "scope": "class",
                "class_name": "高二2403班",
                "expected_students": ["S1"],
            }

        with self.assertRaises(StudentSubmitError) as missing:
            authorize_student_submit_assignment(
                "missing", "S1", load_meta=_load_meta, student_enrolled=lambda *_a, **_k: True
            )
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(StudentSubmitError) as draft:
            authorize_student_submit_assignment(
                "draft", "S1", load_meta=_load_meta, student_enrolled=lambda *_a, **_k: True
            )
        self.assertEqual(draft.exception.detail, "forbidden_assignment_scope")

        with self.assertRaises(StudentSubmitError) as other:
            authorize_student_submit_assignment(
                "HW_1", "S2", load_meta=_load_meta, student_enrolled=lambda *_a, **_k: True
            )
        self.assertEqual(other.exception.detail, "forbidden_assignment_scope")

        with self.assertRaises(StudentSubmitError) as unenrolled:
            authorize_student_submit_assignment(
                "HW_1", "S1", load_meta=_load_meta, student_enrolled=lambda *_a, **_k: False
            )
        self.assertEqual(unenrolled.exception.detail, "forbidden_assignment_scope")

        authorize_student_submit_assignment(
            "HW_1", "S1", load_meta=_load_meta, student_enrolled=lambda *_a, **_k: True
        )

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

    def _assert_ungraded_report_consumed(self, root: Path, *, error_substr: str) -> dict:
        self.assertTrue(list((root / "uploads").glob("*")))
        reports = list((root / "submissions").glob("HW_1/S1/submission_*/grading_report.json"))
        self.assertEqual(len(reports), 1)
        report_path = reports[0]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn(error_substr, str(report.get("error") or ""))
        items = report.get("items") or []
        self.assertTrue(items)
        self.assertEqual(items[0].get("status"), "ungraded")

        copied = list((report_path.parent / "files").glob("*"))
        self.assertEqual(len(copied), 1)
        self.assertEqual(copied[0].read_bytes(), b"1")
        report_files = report.get("files") or []
        self.assertEqual(len(report_files), 1)
        self.assertEqual(Path(report_files[0]).resolve(), copied[0].resolve())

        deps = _attempt_deps(root)
        self.assertFalse(counted_grade_item(items[0], deps=deps))
        attempt = compute_submission_attempt(report_path.parent, deps=deps)
        self.assertIsNotNone(attempt)
        assert attempt is not None
        self.assertFalse(attempt["valid_submission"])
        self.assertEqual(attempt["graded_total"], 0)
        attempts = list_submission_attempts("HW_1", "S1", deps=deps)
        self.assertEqual(len(attempts), 1)
        self.assertIsNone(best_submission_attempt(attempts))
        return report

    async def test_submit_catches_run_script_http_500_as_ungraded_200(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def _boom(_args):
                raise HTTPException(status_code=500, detail="ocr_utils not available")

            deps = _deps(
                root,
                run_script=_boom,
                compute_assignment_progress=lambda assignment_id, include_students: _progress_from_disk(
                    root, assignment_id, include_students
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
            self.assertFalse(result.get("submitted"))
            self.assertEqual(result.get("reason"), "min_graded_total")
            self._assert_ungraded_report_consumed(root, error_substr="ocr_utils not available")

    async def test_submit_catches_run_script_timeout_as_ungraded_200(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def _timeout(_args):
                raise TimeoutExpired(cmd=["python3"], timeout=1)

            deps = _deps(
                root,
                run_script=_timeout,
                compute_assignment_progress=lambda assignment_id, include_students: _progress_from_disk(
                    root, assignment_id, include_students
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
            self.assertFalse(result.get("submitted"))
            self.assertEqual(result.get("reason"), "min_graded_total")
            self._assert_ungraded_report_consumed(root, error_substr="grade_script_timeout")


class StudentSubmitServiceImportGuardTest(unittest.TestCase):
    def test_student_submit_service_does_not_import_fastapi(self):
        from pathlib import Path

        source = Path("services/api/student_submit_service.py").read_text(encoding="utf-8")
        self.assertNotIn("from fastapi", source)
        self.assertNotIn("import fastapi", source)


if __name__ == "__main__":
    unittest.main()
