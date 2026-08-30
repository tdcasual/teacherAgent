from __future__ import annotations

import asyncio
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_catalog_service import (
    AssignmentMetaPostprocessDeps,
    postprocess_assignment_meta,
)
from services.api.assignment_generate_service import (
    AssignmentGenerateDeps,
    AssignmentGenerateError,
    generate_assignment,
)
from services.api.assignment_generate_tool_service import (
    AssignmentGenerateToolDeps,
    assignment_generate,
)
from services.api.assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    AssignmentUploadConfirmError,
    confirm_assignment_upload,
)
from services.api.assignment_upload_start_service import (
    AssignmentUploadStartDeps,
    AssignmentUploadStartError,
    start_assignment_upload,
)
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal
from services.api.paths import InvalidAssignmentDate, optional_assignment_date, parse_date_str
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "student-coach" / "scripts"
sys.path.insert(0, str(SCRIPT))
import select_practice  # type: ignore  # noqa: E402


class _FakeUpload:
    def __init__(self, filename: str) -> None:
        self.filename = filename


def _principal(actor_id: str = "t_zhang") -> AuthPrincipal:
    return AuthPrincipal(actor_id=actor_id, role="teacher", tenant_id="school")


class OptionalAssignmentDateTest(unittest.TestCase):
    def test_empty_none_and_whitespace_stay_none(self) -> None:
        self.assertIsNone(optional_assignment_date(None))
        self.assertIsNone(optional_assignment_date(""))
        self.assertIsNone(optional_assignment_date("   "))

    def test_valid_iso_date(self) -> None:
        self.assertEqual(optional_assignment_date("2026-08-28"), "2026-08-28")
        self.assertEqual(optional_assignment_date("2026-08-28T10:00:00"), "2026-08-28")

    def test_invalid_raises_invalid_assignment_date(self) -> None:
        with self.assertRaises(InvalidAssignmentDate) as cm:
            optional_assignment_date("not-a-date")
        self.assertEqual(str(cm.exception), "invalid_assignment_date")

    def test_parse_date_str_query_semantics_unchanged(self) -> None:
        today = date.today().isoformat()
        self.assertEqual(parse_date_str(None), today)
        self.assertEqual(parse_date_str(""), today)
        self.assertEqual(parse_date_str("2026-02-08"), "2026-02-08")


class AssignmentUploadOwnershipTest(unittest.TestCase):
    def _start_deps(self, root: Path, writes: dict[str, dict]) -> AssignmentUploadStartDeps:
        async def save_upload_file(upload: _FakeUpload, dest: Path) -> int:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"from:{upload.filename}", encoding="utf-8")
            return len(upload.filename)

        return AssignmentUploadStartDeps(
            new_job_id=lambda: "job_own_001",
            optional_assignment_date=optional_assignment_date,
            upload_job_path=lambda job_id: root / "assignment_jobs" / job_id,
            sanitize_filename=lambda name: str(name or "").strip(),
            save_upload_file=save_upload_file,
            parse_ids_value=lambda value: [
                item.strip() for item in str(value or "").split(",") if item.strip()
            ],
            resolve_scope=lambda scope, _student_ids, _class_name: str(scope or "public"),
            normalize_due_at=lambda value: str(value or "").strip() or None,
            now_iso=lambda: "2026-08-28T12:00:00",
            write_upload_job=lambda job_id, updates, overwrite=False: writes.setdefault(
                job_id, {**updates, "_overwrite": overwrite}
            ),
            enqueue_upload_job=lambda _job_id: None,
            diag_log=lambda _event, _payload=None: None,
        )

    def _start(self, root: Path, writes: dict[str, dict], **overrides: object) -> dict:
        kwargs = {
            "assignment_id": "HW_1",
            "date": "",
            "due_at": "",
            "subject_id": "physics",
            "scope": "public",
            "class_name": "",
            "student_ids": "",
            "files": [_FakeUpload("paper.pdf")],
            "answer_files": None,
            "ocr_mode": "FREE_OCR",
            "language": "zh",
            "deps": self._start_deps(root, writes),
        }
        kwargs.update(overrides)
        return asyncio.run(start_assignment_upload(**kwargs))  # type: ignore[arg-type]

    def test_empty_date_and_due_stay_empty(self) -> None:
        token = set_current_principal(_principal())
        try:
            with TemporaryDirectory() as td:
                writes: dict[str, dict] = {}
                result = self._start(Path(td), writes)
                self.assertTrue(result.get("ok"))
                job = writes["job_own_001"]
                self.assertEqual(job.get("date"), "")
                self.assertIn(job.get("due_at"), ("", None))
                self.assertNotEqual(job.get("date"), date.today().isoformat())
                self.assertEqual(job.get("subject_id"), "physics")
                self.assertEqual(job.get("teacher_id"), "t_zhang")
        finally:
            reset_current_principal(token)

    def test_subject_id_required(self) -> None:
        token = set_current_principal(_principal())
        try:
            with TemporaryDirectory() as td:
                writes: dict[str, dict] = {}
                with self.assertRaises(AssignmentUploadStartError) as cm:
                    self._start(Path(td), writes, subject_id="  ")
                self.assertEqual(cm.exception.status_code, 400)
                self.assertEqual(cm.exception.detail, "subject_id_required")
        finally:
            reset_current_principal(token)

    def test_teacher_id_required_when_principal_missing(self) -> None:
        token = set_current_principal(None)
        try:
            with TemporaryDirectory() as td:
                writes: dict[str, dict] = {}
                with self.assertRaises(AssignmentUploadStartError) as cm:
                    self._start(Path(td), writes)
                self.assertEqual(cm.exception.status_code, 400)
                self.assertEqual(cm.exception.detail, "teacher_id_required")
                self.assertEqual(writes, {})
        finally:
            reset_current_principal(token)

    def test_invalid_write_date_is_400(self) -> None:
        token = set_current_principal(_principal())
        try:
            with TemporaryDirectory() as td:
                writes: dict[str, dict] = {}
                with self.assertRaises(AssignmentUploadStartError) as cm:
                    self._start(Path(td), writes, date="not-a-date")
                self.assertEqual(cm.exception.status_code, 400)
                self.assertEqual(cm.exception.detail, "invalid_assignment_date")
        finally:
            reset_current_principal(token)

    def test_persists_due_at_when_provided(self) -> None:
        token = set_current_principal(_principal())
        try:
            with TemporaryDirectory() as td:
                writes: dict[str, dict] = {}
                self._start(
                    Path(td),
                    writes,
                    date="2026-08-28",
                    due_at="2026-08-29T23:59:59",
                    subject_id="math",
                )
                job = writes["job_own_001"]
                self.assertEqual(job.get("date"), "2026-08-28")
                self.assertEqual(job.get("due_at"), "2026-08-29T23:59:59")
                self.assertEqual(job.get("subject_id"), "math")
        finally:
            reset_current_principal(token)


class AssignmentConfirmOwnershipTest(unittest.TestCase):
    def _deps(self, root: Path, writes: list) -> AssignmentUploadConfirmDeps:
        def write_upload_job(job_id: str, updates: dict) -> dict:
            writes.append((job_id, dict(updates)))
            return updates

        return AssignmentUploadConfirmDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-08-28T12:00:00",
            discussion_complete_marker="[[discussion_complete]]",
            write_upload_job=write_upload_job,
            merge_requirements=lambda base, override, overwrite=True: {
                **(base or {}),
                **(override or {}),
            },
            compute_requirements_missing=lambda req: [] if req.get("subject") else ["subject"],
            write_uploaded_questions=lambda _out, _aid, _questions: [{"question_id": "Q1"}],
            optional_assignment_date=optional_assignment_date,
            save_assignment_requirements=lambda *_args, **_kwargs: None,
            parse_ids_value=lambda value: value if isinstance(value, list) else [],
            resolve_scope=lambda scope, _student_ids, _class_name: str(scope or ""),
            normalize_due_at=lambda value: str(value or "").strip() or None,
            compute_expected_students=lambda *_args, **_kwargs: ["S1"],
            atomic_write_json=lambda path, data: path.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            ),
            copy2=lambda src, dst: dst.write_bytes(src.read_bytes()),
        )

    def _prepare_job_dir(self, root: Path) -> Path:
        job_dir = root / "uploads" / "assignment_jobs" / "job-1"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "parsed.json").write_text(
            json.dumps(
                {
                    "questions": [{"stem": "x"}],
                    "requirements": {"subject": "物理"},
                    "missing": [],
                    "warnings": [],
                    "delivery_mode": "pdf",
                    "autofilled": False,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return job_dir

    def test_confirm_writes_owner_fields_and_published(self) -> None:
        token = set_current_principal(_principal())
        try:
            with TemporaryDirectory() as td:
                root = Path(td)
                writes: list = []
                job_dir = self._prepare_job_dir(root)
                result = confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "A1",
                        "status": "done",
                        "scope": "class",
                        "class_name": "高二2403班",
                        "student_ids": [],
                        "date": "",
                        "due_at": "",
                        "teacher_id": "t_zhang",
                        "subject_id": "physics",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=self._deps(root, writes),
                )
                self.assertTrue(result.get("ok"))
                meta = json.loads(
                    (root / "data" / "assignments" / "A1" / "meta.json").read_text(encoding="utf-8")
                )
                self.assertEqual(meta.get("teacher_id"), "t_zhang")
                self.assertEqual(meta.get("subject_id"), "physics")
                self.assertEqual(meta.get("pack_id"), "physics")
                self.assertEqual(meta.get("visibility_status"), "published")
                self.assertIsNone(meta.get("archived_at"))
                self.assertEqual(meta.get("date"), "")
                self.assertEqual(meta.get("due_at"), "")
                policy = meta.get("completion_policy") or {}
                self.assertFalse(policy.get("requires_discussion"))
                self.assertEqual(policy.get("version"), 2)
                self.assertNotEqual(meta.get("teacher_id"), "teacher")
        finally:
            reset_current_principal(token)

    def test_confirm_requires_subject_id(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            writes: list = []
            job_dir = self._prepare_job_dir(root)
            with self.assertRaises(AssignmentUploadConfirmError) as cm:
                confirm_assignment_upload(
                    "job-1",
                    {
                        "assignment_id": "A1",
                        "status": "done",
                        "scope": "public",
                        "teacher_id": "t_zhang",
                        "subject_id": "",
                    },
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=self._deps(root, writes),
                )
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "subject_id_required")
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "subject_id_required")

    def test_confirm_requires_teacher_id(self) -> None:
        token = set_current_principal(None)
        try:
            with TemporaryDirectory() as td:
                root = Path(td)
                writes: list = []
                job_dir = self._prepare_job_dir(root)
                with self.assertRaises(AssignmentUploadConfirmError) as cm:
                    confirm_assignment_upload(
                        "job-1",
                        {
                            "assignment_id": "A1",
                            "status": "done",
                            "scope": "public",
                            "teacher_id": "",
                            "subject_id": "physics",
                        },
                        job_dir,
                        requirements_override=None,
                        strict_requirements=True,
                        deps=self._deps(root, writes),
                    )
                self.assertEqual(cm.exception.status_code, 400)
                self.assertEqual(cm.exception.detail, "teacher_id_required")
                self.assertEqual(writes[-1][1].get("status"), "failed")
                self.assertEqual(writes[-1][1].get("error"), "teacher_id_required")
        finally:
            reset_current_principal(token)


class AssignmentGenerateDraftTest(unittest.TestCase):
    def _http_deps(self, captured: dict) -> AssignmentGenerateDeps:
        def _run_script(args: list[str]) -> str:
            captured["args"] = list(args)
            return "ok"

        def _postprocess(assignment_id: str, **kwargs: object) -> None:
            captured["postprocess"] = {"assignment_id": assignment_id, **kwargs}

        return AssignmentGenerateDeps(
            app_root=Path("/repo"),
            optional_assignment_date=optional_assignment_date,
            ensure_requirements_for_assignment=lambda *_args: {"ok": True},
            run_script=_run_script,
            postprocess_assignment_meta=_postprocess,
            diag_log=lambda _event, _payload=None: None,
        )

    def test_generate_writes_draft_not_published(self) -> None:
        token = set_current_principal(_principal())
        try:
            captured: dict = {}
            result = generate_assignment(
                assignment_id="HW_1",
                kp="力学",
                question_ids="",
                per_kp=5,
                core_examples="",
                generate=False,
                mode="",
                date="",
                due_at="",
                class_name="",
                student_ids="",
                source="teacher",
                requirements_json=None,
                subject_id="math",
                deps=self._http_deps(captured),
            )
            self.assertTrue(result.get("ok"))
            args = captured["args"]
            self.assertIn("--subject-id", args)
            self.assertIn("math", args)
            self.assertIn("--teacher-id", args)
            self.assertIn("t_zhang", args)
            self.assertNotIn("--date", args)
            post = captured["postprocess"]
            self.assertEqual(post.get("visibility_status"), "draft")
            self.assertNotEqual(post.get("visibility_status"), "published")
            self.assertEqual(post.get("teacher_id"), "t_zhang")
            self.assertEqual(post.get("subject_id"), "math")
            self.assertFalse((post.get("completion_policy") or {}).get("requires_discussion"))
        finally:
            reset_current_principal(token)

    def test_generate_requires_subject_id(self) -> None:
        token = set_current_principal(_principal())
        try:
            with self.assertRaises(AssignmentGenerateError) as cm:
                generate_assignment(
                    assignment_id="HW_1",
                    kp="",
                    question_ids="",
                    per_kp=5,
                    core_examples="",
                    generate=False,
                    mode="",
                    date="2026-08-28",
                    due_at="",
                    class_name="",
                    student_ids="",
                    source="teacher",
                    requirements_json=None,
                    subject_id="",
                    deps=self._http_deps({}),
                )
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "subject_id_required")
        finally:
            reset_current_principal(token)

    def test_generate_tool_stamps_principal_teacher_id_and_draft(self) -> None:
        token = set_current_principal(_principal("t_li"))
        try:
            captured: dict = {"cmd": None, "postprocess": None}

            def _run_script(cmd: list[str]) -> str:
                captured["cmd"] = list(cmd)
                return "done"

            def _postprocess(assignment_id: str, **kwargs: object) -> None:
                captured["postprocess"] = {"assignment_id": assignment_id, **kwargs}

            deps = AssignmentGenerateToolDeps(
                app_root=Path("/repo"),
                optional_assignment_date=optional_assignment_date,
                ensure_requirements_for_assignment=lambda *_args: {"ok": True},
                run_script=_run_script,
                postprocess_assignment_meta=_postprocess,
                diag_log=lambda _event, _payload=None: None,
            )
            result = assignment_generate(
                {
                    "assignment_id": "HW_1",
                    "subject_id": "generic",
                    "teacher_id": "forged_teacher",
                    "date": "",
                    "skip_validation": True,
                },
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            cmd = captured["cmd"]
            self.assertIn("--teacher-id", cmd)
            self.assertIn("t_li", cmd)
            self.assertNotIn("forged_teacher", cmd)
            post = captured["postprocess"]
            self.assertEqual(post.get("visibility_status"), "draft")
            self.assertEqual(post.get("teacher_id"), "t_li")
        finally:
            reset_current_principal(token)


class AssignmentGenerateToolSchemaTest(unittest.TestCase):
    def test_generate_schema_requires_subject_id(self) -> None:
        tool = DEFAULT_TOOL_REGISTRY.require("assignment.generate")
        schema = tool.to_openai()["function"]["parameters"]
        self.assertIn("subject_id", schema.get("properties") or {})
        self.assertIn("due_at", schema.get("properties") or {})
        self.assertIn("subject_id", schema.get("required") or [])


class SelectPracticeMetaDraftTest(unittest.TestCase):
    def test_generated_meta_is_draft_with_owner_fields(self) -> None:
        meta = select_practice.build_generated_assignment_meta(
            assignment_id="HW_1",
            date_str="",
            mode="kp",
            kp_list=["力学"],
            question_ids=["Q1"],
            class_name="",
            student_ids=[],
            scope="public",
            source="teacher",
            teacher_id="t_zhang",
            subject_id="physics",
            due_at="",
            generated_at="2026-08-28T12:00:00",
        )
        self.assertEqual(meta["visibility_status"], "draft")
        self.assertNotEqual(meta["visibility_status"], "published")
        self.assertEqual(meta["teacher_id"], "t_zhang")
        self.assertEqual(meta["subject_id"], "physics")
        self.assertEqual(meta["pack_id"], "physics")
        self.assertEqual(meta["date"], "")
        self.assertEqual(meta["due_at"], "")
        self.assertIsNone(meta["archived_at"])
        self.assertFalse(meta["completion_policy"]["requires_discussion"])
        self.assertEqual(meta["completion_policy"]["version"], 2)

    def test_safe_date_empty_stays_empty(self) -> None:
        self.assertEqual(select_practice.safe_date(""), "")
        self.assertEqual(select_practice.safe_date("   "), "")
        self.assertEqual(select_practice.safe_date("2026-08-28"), "2026-08-28")

    def test_rejects_empty_teacher_id(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            select_practice.build_generated_assignment_meta(
                assignment_id="HW_1",
                date_str="",
                mode="kp",
                kp_list=["力学"],
                question_ids=["Q1"],
                class_name="",
                student_ids=[],
                scope="public",
                source="teacher",
                teacher_id="  ",
                subject_id="physics",
                due_at="",
                generated_at="2026-08-28T12:00:00",
            )
        self.assertEqual(str(cm.exception), "teacher_id_required")

    def test_rejects_empty_subject_id(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            select_practice.build_generated_assignment_meta(
                assignment_id="HW_1",
                date_str="",
                mode="kp",
                kp_list=["力学"],
                question_ids=["Q1"],
                class_name="",
                student_ids=[],
                scope="public",
                source="teacher",
                teacher_id="t_zhang",
                subject_id="",
                due_at="",
                generated_at="2026-08-28T12:00:00",
            )
        self.assertEqual(str(cm.exception), "subject_id_required")


class PostprocessOwnerFieldsTest(unittest.TestCase):
    def test_postprocess_can_stamp_draft_owner_fields(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "data" / "assignments" / "HW_1"
            folder.mkdir(parents=True, exist_ok=True)
            meta_path = folder / "meta.json"
            meta_path.write_text(json.dumps({"assignment_id": "HW_1"}), encoding="utf-8")

            deps = AssignmentMetaPostprocessDeps(
                data_dir=root / "data",
                discussion_complete_marker="[DISCUSS_OK]",
                load_profile_file=lambda path: json.loads(path.read_text(encoding="utf-8")),
                parse_ids_value=lambda value: [],
                resolve_scope=lambda scope, _student_ids, _class_name: str(scope or "public"),
                normalize_due_at=lambda value: str(value or "").strip() or None,
                compute_expected_students=lambda *_args, **_kwargs: [],
                atomic_write_json=lambda path, payload: path.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                ),
                now_iso=lambda: "2026-08-28T12:00:00",
            )
            postprocess_assignment_meta(
                assignment_id="HW_1",
                due_at="",
                expected_students=None,
                completion_policy={"requires_discussion": False, "version": 2},
                deps=deps,
                visibility_status="draft",
                teacher_id="t_zhang",
                subject_id="generic",
            )
            updated = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(updated.get("visibility_status"), "draft")
            self.assertEqual(updated.get("teacher_id"), "t_zhang")
            self.assertEqual(updated.get("subject_id"), "generic")
            self.assertEqual(updated.get("pack_id"), "generic")
            self.assertEqual(updated.get("due_at"), "")


if __name__ == "__main__":
    unittest.main()
