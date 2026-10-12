import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from services.api.assignment_progress_service import (
    AssignmentProgressDeps,
    compute_assignment_progress,
)
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


def _real_progress(root: Path, assignment_id: str, include_students: bool = True) -> dict:
    attempt_deps = _attempt_deps(root)

    def _load_meta(folder):
        path = Path(folder) / "meta.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(path, payload):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    deps = AssignmentProgressDeps(
        data_dir=root,
        load_assignment_meta=_load_meta,
        postprocess_assignment_meta=lambda _aid: None,
        normalize_due_at=lambda v: v or "",
        list_all_student_profiles=lambda: [],
        session_discussion_pass=lambda _s, _a: {},
        list_submission_attempts=lambda aid, sid: list_submission_attempts(
            aid, sid, deps=attempt_deps
        ),
        best_submission_attempt=best_submission_attempt,
        resolve_assignment_date=lambda _m, _f: "2026-01-01",
        atomic_write_json=_write_json,
        today_iso=lambda: "2026-01-15",
        now_iso=lambda: "2026-01-15T00:00:00Z",
    )
    return compute_assignment_progress(
        assignment_id, deps=deps, include_students=include_students
    )


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

        with self.assertRaises(StudentSubmitError) as sql_miss:
            authorize_student_submit_assignment(
                "HW_1",
                "S1",
                load_meta=_load_meta,
                student_enrolled=lambda *_a, **_k: True,
                is_sql_published=lambda _aid: False,
            )
        self.assertEqual(sql_miss.exception.detail, "forbidden_assignment_scope")

        authorize_student_submit_assignment(
            "HW_1",
            "S1",
            load_meta=_load_meta,
            student_enrolled=lambda *_a, **_k: True,
            is_sql_published=lambda _aid: True,
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
            self.assertIn("--skip-profile-update", args)
            self.assertNotIn("--attempt-dir", args)
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

    def _write_assignment(self, root: Path, *, questions: str, requirements: dict | None = None) -> None:
        folder = root / "assignments" / "HW_1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "questions.csv").write_text(questions, encoding="utf-8")
        (folder / "requirements.json").write_text(
            json.dumps(requirements or {}, ensure_ascii=False),
            encoding="utf-8",
        )
        (folder / "meta.json").write_text("{}", encoding="utf-8")

    async def test_submit_writes_derived_profile_from_grading_report(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_assignment(
                root,
                questions=(
                    "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
                    "Q1,力学,basic,open,,,,\n"
                    "Q2,热学,basic,open,,,,\n"
                ),
            )

            def _run(_args):
                attempt = root / "submissions" / "HW_1" / "S1" / "submission_20260101_000000"
                attempt.mkdir(parents=True, exist_ok=True)
                (attempt / "grading_report.json").write_text(
                    json.dumps(
                        {
                            "graded_total": 2,
                            "correct": 1,
                            "items": [
                                {"question_id": "Q1", "kp_id": "力学", "status": "missed", "score": 0},
                                {"question_id": "Q2", "kp_id": "热学", "status": "matched", "score": 1},
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                return "ok"

            deps = _deps(root, run_script=_run, data_dir=root)
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            profile = json.loads((root / "student_profiles" / "S1.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["recent_weak_kp"], ["力学"])
            self.assertEqual(profile["recent_strong_kp"], ["热学"])
            self.assertEqual(profile["next_focus"], "力学")

    async def test_all_correct_report_replaces_weak_kp_with_empty_list(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_assignment(
                root,
                questions="question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\nQ1,力学,basic,open,,,,\n",
            )
            profile_path = root / "student_profiles" / "S1.json"
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(
                json.dumps({"recent_weak_kp": ["力学"], "next_focus": "力学"}),
                encoding="utf-8",
            )

            def _run(_args):
                attempt = root / "submissions" / "HW_1" / "S1" / "submission_20260101_000000"
                attempt.mkdir(parents=True, exist_ok=True)
                (attempt / "grading_report.json").write_text(
                    json.dumps(
                        {
                            "graded_total": 1,
                            "correct": 1,
                            "items": [
                                {"question_id": "Q1", "kp_id": "力学", "status": "matched", "score": 1},
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                return "ok"

            deps = _deps(root, run_script=_run, data_dir=root)
            await submit(
                student_id="S1",
                files=[_Upload(filename="a1.pdf", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["recent_weak_kp"], [])
            self.assertEqual(profile["recent_strong_kp"], ["力学"])
            self.assertEqual(profile["next_focus"], "")

    async def test_ungraded_submit_writes_fallback_kp_from_requirements(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_assignment(
                root,
                questions="question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\nQ1,力学,basic,open,,,,\n",
                requirements={"core_concepts": ["牛顿定律", "受力分析", "加速度"]},
            )

            def _boom(_args):
                raise HTTPException(status_code=500, detail="ocr_utils not available")

            deps = _deps(
                root,
                run_script=_boom,
                data_dir=root,
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
            profile = json.loads((root / "student_profiles" / "S1.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["recent_weak_kp"], ["牛顿定律", "受力分析", "加速度"])
            self.assertEqual(profile["practice_history"][0]["source"], "ungraded_fallback")

    async def test_zero_question_submit_is_received_without_items(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_assignment(
                root,
                questions="question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n",
                requirements={"discussion_goals": ["描述现象"]},
            )
            called = {"run": 0}

            def _run(_args):
                called["run"] += 1
                return "should_not_run"

            deps = _deps(
                root,
                run_script=_run,
                data_dir=root,
                compute_assignment_progress=lambda assignment_id, include_students: _progress_from_disk(
                    root, assignment_id, include_students
                ),
            )
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="photo.jpg", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertEqual(called["run"], 0)
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("submitted"))
            self.assertIsNone(result.get("official_score"))
            reports = list((root / "submissions").glob("HW_1/S1/submission_*/grading_report.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertTrue(report.get("received_without_items"))
            self.assertEqual(report.get("items"), [])
            attempt = compute_submission_attempt(reports[0].parent, deps=_attempt_deps(root))
            self.assertIsNotNone(attempt)
            assert attempt is not None
            self.assertTrue(attempt["valid_submission"])
            attempts = list_submission_attempts("HW_1", "S1", deps=_attempt_deps(root))
            self.assertEqual(len(attempts), 1)
            profile = json.loads((root / "student_profiles" / "S1.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["recent_weak_kp"], ["描述现象"])
            self.assertEqual(profile["practice_history"][0]["source"], "brief_fallback")

    async def test_zero_question_submit_official_score_null_via_real_progress(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "HW_1"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "questions.csv").write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n",
                encoding="utf-8",
            )
            (folder / "requirements.json").write_text("{}", encoding="utf-8")
            (folder / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_1",
                        "expected_students": ["S1"],
                        "assignment_kind": "practical",
                        "completion_policy": {"min_graded_total": 0, "requires_submission": True},
                    }
                ),
                encoding="utf-8",
            )
            deps = _deps(
                root,
                data_dir=root,
                compute_assignment_progress=lambda assignment_id, include_students: _real_progress(
                    root, assignment_id, include_students
                ),
            )
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="photo.jpg", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("submitted"))
            self.assertIsNone(result.get("official_score"))
            progress = _real_progress(root, "HW_1", True)
            student = progress["students"][0]
            self.assertTrue(student["submitted"])
            self.assertIsNone(student["official_score"])
            self.assertIsNone(student["evidence"]["signals"]["official_score"])
            self.assertIsNone(student["evidence"]["signals"]["best_score_earned"])

    def _prepare_assignment_sql(self, root: Path) -> None:
        from services.api.assignment.store import connect, ensure

        conn = connect(root)
        try:
            ensure(conn, data_dir=root)
        finally:
            conn.close()

    def _attempt_sql_row(self, root: Path, assignment_id: str, student_id: str):
        from services.api.assignment.store import connect

        conn = connect(root)
        try:
            return conn.execute(
                "SELECT attempt_id, submitted_at, grading_report_json, files_json "
                "FROM student_submission_attempts "
                "WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, student_id),
            ).fetchone()
        finally:
            conn.close()

    async def test_submit_upserts_attempt_sql(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._prepare_assignment_sql(root)

            def _run_script(_args):
                attempt = root / "submissions" / "HW_1" / "S1" / "submission_20260115_000000"
                attempt.mkdir(parents=True, exist_ok=True)
                report = {
                    "student_id": "S1",
                    "assignment_id": "HW_1",
                    "graded_total": 1,
                    "score_earned": 8,
                    "submitted_at": "2026-01-15T00:00:00",
                }
                (attempt / "grading_report.json").write_text(
                    json.dumps(report, ensure_ascii=False), encoding="utf-8"
                )
                (attempt / "page1.pdf").write_bytes(b"%PDF")
                return "ok"

            deps = _deps(
                root,
                run_script=_run_script,
                compute_assignment_progress=lambda _assignment_id, _include_students: _progress(
                    submitted=True, score=8.0, attempt_id="submission_20260115_000000"
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
            row = self._attempt_sql_row(root, "HW_1", "S1")
            self.assertIsNotNone(row)
            self.assertEqual(row["attempt_id"], "submission_20260115_000000")
            report = json.loads(row["grading_report_json"])
            self.assertEqual(report.get("graded_total"), 1)
            self.assertEqual(report.get("score_earned"), 8)
            files = json.loads(row["files_json"])
            self.assertIn("grading_report.json", files)
            self.assertIn("page1.pdf", files)

    async def test_ungraded_submit_upserts_attempt_sql(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._prepare_assignment_sql(root)

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
            row = self._attempt_sql_row(root, "HW_1", "S1")
            self.assertIsNotNone(row)
            self.assertTrue(str(row["attempt_id"]).startswith("submission_"))
            report = json.loads(row["grading_report_json"])
            self.assertEqual(report.get("ungraded"), 1)
            self.assertIn("ocr_utils not available", str(report.get("error") or ""))

    def _write_non_problem_set_zero_row(self, root: Path, *, kind: str = "scenario") -> None:
        folder = root / "assignments" / "HW_1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "questions.csv").write_text(
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n",
            encoding="utf-8",
        )
        (folder / "requirements.json").write_text("{}", encoding="utf-8")
        (folder / "meta.json").write_text(
            json.dumps(
                {
                    "assignment_id": "HW_1",
                    "assignment_kind": kind,
                    "expected_students": ["S1"],
                    "completion_policy": {"min_graded_total": 0, "requires_submission": True},
                }
            ),
            encoding="utf-8",
        )

    async def test_zero_question_submit_writes_pending_rubric_suggestion(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_non_problem_set_zero_row(root)
            deps = _deps(
                root,
                data_dir=root,
                student_submissions_dir=root / "student_submissions",
                compute_assignment_progress=lambda assignment_id, include_students: {
                    "ok": True,
                    "students": [
                        {
                            "student_id": "S1",
                            "evidence": {
                                "schema": "assignment_progress_evidence/v1",
                                "signals": {
                                    "submitted": True,
                                    "best_graded_total": 0,
                                    "best_score_earned": None,
                                    "best_attempt_id": "submission_1",
                                    "min_graded_total": 0,
                                    "official_score": None,
                                },
                            },
                        }
                    ],
                },
            )
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="photo.jpg", content=b"1")],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("submitted"))
            self.assertIsNone(result.get("official_score"))
            suggestion_path = (
                root / "student_submissions" / "HW_1" / "S1" / "rubric_suggestion.json"
            )
            self.assertTrue(suggestion_path.is_file())
            payload = json.loads(suggestion_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "assignment_rubric_suggestion/v1")
            self.assertEqual(payload.get("status"), "pending")
            self.assertIsNone(payload.get("suggested_score"))

    async def test_non_problem_set_submit_does_not_wait_for_rubric_llm(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_non_problem_set_zero_row(root)
            enqueued = []
            llm_calls = {"n": 0}

            def _generate(*_args, **_kwargs):
                llm_calls["n"] += 1
                raise AssertionError("submit must not wait for rubric LLM")

            def _trigger(**kwargs):
                enqueued.append(dict(kwargs))
                return {}

            deps = _deps(
                root,
                data_dir=root,
                student_submissions_dir=root / "student_submissions",
                trigger_rubric_suggest=_trigger,
                compute_assignment_progress=lambda assignment_id, include_students: _progress(
                    submitted=True, score=0.0, attempt_id="submission_1"
                ),
            )
            from unittest.mock import patch

            with patch("llm_gateway.LLMGateway.generate", _generate):
                result = await submit(
                    student_id="S1",
                    files=[_Upload(filename="photo.jpg", content=b"1")],
                    assignment_id="HW_1",
                    auto_assignment=False,
                    deps=deps,
                )
            self.assertTrue(result.get("ok"))
            self.assertEqual(llm_calls["n"], 0)
            self.assertEqual(len(enqueued), 1)
            self.assertEqual(enqueued[0]["job_kind"], "rubric_suggest")
            self.assertTrue(str(enqueued[0]["attempt_id"]).startswith("submission_"))

    async def test_rubric_suggest_enqueue_includes_attempt_id(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._write_non_problem_set_zero_row(root, kind="practical")
            enqueued = []

            def _trigger(**kwargs):
                enqueued.append(dict(kwargs))
                return {}

            deps = _deps(
                root,
                data_dir=root,
                student_submissions_dir=root / "student_submissions",
                trigger_rubric_suggest=_trigger,
                compute_assignment_progress=lambda assignment_id, include_students: _progress(
                    submitted=True, score=0.0
                ),
            )
            result = await submit(
                student_id="S1",
                files=[_Upload(filename="notes.md", content="# 观察记录".encode("utf-8"))],
                assignment_id="HW_1",
                auto_assignment=False,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(len(enqueued), 1)
            payload = enqueued[0]
            self.assertEqual(payload["job_kind"], "rubric_suggest")
            self.assertEqual(payload["assignment_id"], "HW_1")
            self.assertEqual(payload["student_id"], "S1")
            attempt_id = str(payload["attempt_id"] or "")
            self.assertTrue(attempt_id.startswith("submission_"))
            attempt_dir = root / "student_submissions" / "HW_1" / "S1" / attempt_id
            self.assertTrue(attempt_dir.is_dir())

    async def test_non_problem_set_submit_skips_llm_without_text(self):
        from services.api.assignment_rubric_service import run_rubric_suggest_job

        with TemporaryDirectory() as td:
            root = Path(td)
            attempt_id = "submission_20260115_000000"
            attempt_dir = root / "student_submissions" / "HW_1" / "S1" / attempt_id
            attempt_dir.mkdir(parents=True, exist_ok=True)
            (attempt_dir / "photo.jpg").write_bytes(b"\xff\xd8")
            llm_calls = {"n": 0}

            class _Gateway:
                def resolve_target(self):
                    raise AssertionError("no-text path must not resolve LLM target")

                def generate(self, *_args, **_kwargs):
                    llm_calls["n"] += 1
                    raise AssertionError("no-text path must not call LLM")

            result = run_rubric_suggest_job(
                {
                    "job_kind": "rubric_suggest",
                    "assignment_id": "HW_1",
                    "student_id": "S1",
                    "attempt_id": attempt_id,
                },
                data_dir=root,
                gateway=_Gateway(),
                diag_log=lambda _event, _payload: None,
            )
            self.assertEqual(result.get("status"), "ready")
            self.assertEqual(result.get("source"), "heuristic_none")
            self.assertIsNone(result.get("suggested_score"))
            self.assertEqual(llm_calls["n"], 0)
            saved = json.loads(
                (root / "student_submissions" / "HW_1" / "S1" / "rubric_suggestion.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved.get("source"), "heuristic_none")
            self.assertIsNone(saved.get("suggested_score"))
            self.assertIn("无文本摘录", str(saved.get("comment") or ""))


class StudentSubmitServiceImportGuardTest(unittest.TestCase):
    def test_student_submit_service_does_not_import_fastapi(self):
        from pathlib import Path

        source = Path("services/api/student_submit_service.py").read_text(encoding="utf-8")
        self.assertNotIn("from fastapi", source)
        self.assertNotIn("import fastapi", source)


if __name__ == "__main__":
    unittest.main()
