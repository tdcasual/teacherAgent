import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment.store import connect, ensure, get_assignment, upsert_assignment
from services.api.assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    AssignmentUploadConfirmError,
    _finalize_published_from_folder,
    _snapshot_bank_refs,
    confirm_assignment_upload,
)
from services.api.auth.identity_graph_service import ExpectedStudentsError
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal
from services.api.question_bank_select_service import read_question_bank


class AssignmentUploadConfirmServiceTest(unittest.TestCase):
    def _deps(self, root: Path, writes: list):  # type: ignore[no-untyped-def]
        def write_upload_job(job_id, updates):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates)))
            return updates

        return AssignmentUploadConfirmDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-02-08T12:00:00",
            discussion_complete_marker="[[discussion_complete]]",
            write_upload_job=write_upload_job,
            merge_requirements=lambda base, override, overwrite=True: {
                **(base or {}),
                **(override or {}),
            },
            compute_requirements_missing=lambda req, **_k: [] if req.get("subject") else ["subject"],
            write_uploaded_questions=lambda _out, _aid, _questions: [{"question_id": "Q1"}],
            optional_assignment_date=lambda v: str(v).strip() if str(v or "").strip() else None,
            save_assignment_requirements=lambda *_args, **_kwargs: None,
            parse_ids_value=lambda value: value if isinstance(value, list) else [],
            resolve_scope=lambda scope, _student_ids, _class_name: str(scope or ""),
            normalize_due_at=lambda value: str(value or ""),
            compute_expected_students=lambda *_args, **_kwargs: [],
            atomic_write_json=lambda path, data: path.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            ),
            copy2=lambda src, dst: dst.write_bytes(src.read_bytes()),
        )

    def test_missing_parsed_marks_failed_and_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {"assignment_id": "A1", "status": "done"},
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "parsed result missing")
            self.assertEqual(writes[-1][1].get("status"), "failed")

    def test_strict_missing_requirements_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            parsed = {
                "questions": [{"stem": "x"}],
                "requirements": {},
                "missing": ["subject"],
                "warnings": [],
            }
            (job_dir / "parsed.json").write_text(
                json.dumps(parsed, ensure_ascii=False), encoding="utf-8"
            )
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {"assignment_id": "A1", "status": "done"},
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail.get("error"), "requirements_missing")

    def test_success_writes_meta_and_returns_ok(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            (job_dir / "source").mkdir(parents=True, exist_ok=True)
            (job_dir / "answer_source").mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": ["w1"],
                        "delivery_mode": "pdf",
                        "autofilled": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            result = confirm_assignment_upload(
                "job-1",
                {
                    "assignment_id": "A1",
                    "status": "done",
                    "scope": "class",
                    "class_name": "高二2403班",
                    "student_ids": [],
                    "date": "2026-02-08",
                    "teacher_id": "t_zhang",
                    "subject_id": "physics",
                },
                job_dir,
                requirements_override=None,
                strict_requirements=True,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("assignment_id"), "A1")
            meta_path = root / "data" / "assignments" / "A1" / "meta.json"
            self.assertTrue(meta_path.exists())
            self.assertEqual(writes[-1][1].get("status"), "confirmed")
            from services.api.assignment.store import connect, get_assignment

            conn = connect(root / "data")
            try:
                row = get_assignment(conn, "A1")
            finally:
                conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row["visibility_status"], "published")
            self.assertEqual(row["teacher_id"], "t_zhang")

    def test_rejects_invalid_assignment_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "../escape",
                        "status": "done",
                        "teacher_id": "t_zhang",
                        "subject_id": "physics",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "invalid assignment_id")
            self.assertEqual(writes[-1][1].get("status"), "failed")

    def test_confirm_maps_roster_required(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            def _raise_roster(*_args, **_kwargs):
                raise ExpectedStudentsError("roster_required")

            deps = replace(self._deps(root, writes), compute_expected_students=_raise_roster)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "HW-1",
                        "status": "done",
                        "teacher_id": "t_zhang",
                        "subject_id": "physics",
                        "scope": "class",
                        "class_name": "高二2403班",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "roster_required")
            self.assertEqual(writes[-1][1].get("status"), "failed")

    def test_json_write_failure_rolls_back_sql_and_does_not_unlink(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            def _write_then_fail(path, data):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                raise OSError("fsync failed")

            deps = replace(self._deps(root, writes), atomic_write_json=_write_then_fail)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "A1",
                        "status": "done",
                        "teacher_id": "t_zhang",
                        "subject_id": "physics",
                        "scope": "public",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 500)
            meta_path = root / "data" / "assignments" / "A1" / "meta.json"
            self.assertTrue(meta_path.exists())
            from services.api.assignment.store import connect, get_assignment

            conn = connect(root / "data")
            try:
                self.assertIsNone(get_assignment(conn, "A1"))
            finally:
                conn.close()

    def test_existing_sql_and_json_still_conflict(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            confirm_assignment_upload(
                "job-1",
                {
                    "assignment_id": "A1",
                    "status": "done",
                    "teacher_id": "t_zhang",
                    "subject_id": "physics",
                    "scope": "public",
                },
                job_dir,
                requirements_override=None,
                strict_requirements=True,
                deps=deps,
            )
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "A1",
                        "status": "done",
                        "teacher_id": "t_zhang",
                        "subject_id": "physics",
                        "scope": "public",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(ctx.exception.detail, "assignment already exists")

    def _eight_point(self):
        return {
            "subject": "物理",
            "topic": "电流",
            "grade_level": "初二",
            "class_level": "中等",
            "core_concepts": ["电流", "电压", "电阻"],
            "typical_problem": "串并联",
            "misconceptions": ["错1", "错2", "错3", "错4"],
            "duration_minutes": 40,
            "preferences": ["A基础"],
        }

    def _write_draft_folder(self, root: Path, assignment_id: str, *, kind="problem_set", extra_req=None):
        folder = root / "data" / "assignments" / assignment_id
        folder.mkdir(parents=True, exist_ok=True)
        req = self._eight_point()
        if extra_req:
            req.update(extra_req)
        (folder / "requirements.json").write_text(
            json.dumps({"assignment_id": assignment_id, **req}, ensure_ascii=False),
            encoding="utf-8",
        )
        (folder / "questions.csv").write_text(
            "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
            "Q1,kp1,basic,open,stem.md,ans.md,bank,\n",
            encoding="utf-8",
        )
        meta = {
            "assignment_id": assignment_id,
            "teacher_id": "t_zhang",
            "subject_id": "physics",
            "visibility_status": "draft",
            "assignment_kind": kind,
            "content_source": "bank" if kind == "problem_set" else "upload",
            "scope": "public",
            "class_name": "",
            "student_ids": [],
        }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return folder

    def test_confirm_from_assignment_id_publishes_draft_folder(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            self._write_draft_folder(root, "A_FOLDER")
            deps = self._deps(root, writes)
            token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
            try:
                result = _finalize_published_from_folder(
                    "A_FOLDER",
                    requirements_override=None,
                    completion_policy_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            finally:
                reset_current_principal(token)
            self.assertTrue(result.get("ok"))
            meta = json.loads(
                (root / "data" / "assignments" / "A_FOLDER" / "meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual(meta.get("visibility_status"), "published")
            self.assertEqual(meta.get("content_source"), "bank")
            self.assertEqual(meta.get("assignment_kind"), "problem_set")
            self.assertIn("allow_practice", meta.get("completion_policy") or {})

    def test_confirm_existing_draft_is_not_assignment_already_exists(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            self._write_draft_folder(root, "A_EXISTING")
            deps = self._deps(root, writes)
            conn = connect(root / "data")
            try:
                ensure(conn, data_dir=root / "data")
                upsert_assignment(
                    conn,
                    json.loads(
                        (root / "data" / "assignments" / "A_EXISTING" / "meta.json").read_text(
                            encoding="utf-8"
                        )
                    ),
                    now_iso="2026-02-08T12:00:00",
                )
                conn.commit()
            finally:
                conn.close()
            token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
            try:
                result = _finalize_published_from_folder(
                    "A_EXISTING",
                    strict_requirements=True,
                    deps=deps,
                )
            finally:
                reset_current_principal(token)
            self.assertTrue(result.get("ok"))
            self.assertNotEqual(result.get("error"), "assignment already exists")
            conn = connect(root / "data")
            try:
                row = get_assignment(conn, "A_EXISTING")
            finally:
                conn.close()
            self.assertEqual(row["visibility_status"], "published")

    def test_confirm_writes_kind_and_content_source(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            (job_dir / "source").mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            confirm_assignment_upload(
                "job-1",
                {
                    "assignment_id": "A_KIND",
                    "status": "done",
                    "scope": "public",
                    "teacher_id": "t_zhang",
                    "subject_id": "physics",
                    "assignment_kind": "problem_set",
                },
                job_dir,
                requirements_override=None,
                strict_requirements=True,
                deps=deps,
            )
            meta = json.loads(
                (root / "data" / "assignments" / "A_KIND" / "meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual(meta.get("content_source"), "upload")
            self.assertEqual(meta.get("assignment_kind"), "problem_set")
            self.assertEqual(meta.get("mode"), "upload")
            self.assertTrue((meta.get("completion_policy") or {}).get("allow_practice"))

    def test_problem_set_confirm_requires_questions(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "A0",
                        "status": "done",
                        "teacher_id": "t_zhang",
                        "subject_id": "physics",
                        "assignment_kind": "problem_set",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "questions_missing")

    def test_snapshot_bank_refs_rejects_out_of_jail(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            bank = data_dir / "question_bank"
            bank.mkdir(parents=True)
            good = bank / "ok.md"
            good.write_text("in-jail", encoding="utf-8")
            secret = root / "secret.md"
            secret.write_text("SECRET", encoding="utf-8")
            folder = data_dir / "assignments" / "A_SNAP"
            folder.mkdir(parents=True)
            (folder / "questions.csv").write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
                f"../x,kp1,basic,open,{secret},{good},bank,\n",
                encoding="utf-8",
            )
            _snapshot_bank_refs(folder, app_root=root, data_dir=data_dir)
            rows = read_question_bank(folder / "questions.csv")
            self.assertEqual(rows[0].get("stem_ref"), "")
            self.assertTrue(str(rows[0].get("answer_ref") or ""))
            stem_dir = folder / "bank_stems"
            if stem_dir.exists():
                for path in stem_dir.iterdir():
                    self.assertNotIn("SECRET", path.read_text(encoding="utf-8"))

    def test_finalize_rejects_unsafe_assignment_id(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, writes=[])
            token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
            try:
                for aid in (".", "../escape"):
                    with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                        _finalize_published_from_folder(aid, strict_requirements=True, deps=deps)
                    self.assertEqual(ctx.exception.status_code, 400)
                    self.assertEqual(ctx.exception.detail, "invalid assignment_id")
            finally:
                reset_current_principal(token)

    def test_finalize_non_owner_published_is_403(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = self._write_draft_folder(root, "A_PUB")
            meta_path = folder / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["visibility_status"] = "published"
            meta["teacher_id"] = "t_other"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            deps = self._deps(root, writes=[])
            token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
            try:
                with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                    _finalize_published_from_folder("A_PUB", strict_requirements=True, deps=deps)
            finally:
                reset_current_principal(token)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail, "forbidden")
            saved = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(saved.get("visibility_status"), "published")


if __name__ == "__main__":
    unittest.main()
