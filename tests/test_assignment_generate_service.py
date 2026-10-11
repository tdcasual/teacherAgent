import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_generate_service import (
    AssignmentGenerateDeps,
    AssignmentGenerateError,
    generate_assignment,
)
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal


class AssignmentGenerateServiceTest(unittest.TestCase):
    def _deps(self):
        captured = {"args": None, "log": []}

        def _run_script(args):
            captured["args"] = list(args)
            return "ok"

        deps = AssignmentGenerateDeps(
            app_root=Path("/repo"),
            optional_assignment_date=lambda value: (
                str(value).strip() if str(value or "").strip() else None
            ),
            ensure_requirements_for_assignment=lambda *_args: {"ok": True},
            run_script=_run_script,
            postprocess_assignment_meta=lambda *_args, **_kwargs: None,
            diag_log=lambda event, payload=None: captured["log"].append((event, payload or {})),
        )
        return deps, captured

    def test_invalid_requirements_json_raises_400(self):
        deps, _captured = self._deps()

        with self.assertRaises(AssignmentGenerateError) as cm:
            generate_assignment(
                assignment_id="HW_1",
                kp="",
                question_ids="",
                per_kp=5,
                core_examples="",
                generate=False,
                mode="",
                date="2026-02-08",
                due_at="",
                class_name="",
                student_ids="",
                source="",
                requirements_json="{bad-json",
                deps=deps,
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "requirements_json is not valid JSON")

    def test_requirements_error_raises_400(self):
        deps, _captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{
                **deps.__dict__,
                "ensure_requirements_for_assignment": lambda *_args: {
                    "error": "missing_requirements"
                },
            }
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
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
                    date="2026-02-08",
                    due_at="",
                    class_name="",
                    student_ids="",
                    source="teacher",
                    requirements_json=None,
                    subject_id="physics",
                    deps=deps,
                )
        finally:
            reset_current_principal(token)

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail.get("error"), "missing_requirements")

    def test_success_builds_command_and_logs_postprocess_error(self):
        deps, captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{
                **deps.__dict__,
                "postprocess_assignment_meta": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("boom")
                ),
            }
        )

        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            result = generate_assignment(
                assignment_id="HW_1",
                kp="力学",
                question_ids="Q1,Q2",
                per_kp=3,
                core_examples="EX_A",
                generate=True,
                mode="auto",
                date="2026-02-08",
                due_at="2026-02-09T20:00:00",
                class_name="高二2403班",
                student_ids="S1,S2",
                source="teacher",
                requirements_json='{"core_concepts":["力"]}',
                subject_id="physics",
                deps=deps,
            )
        finally:
            reset_current_principal(token)

        self.assertEqual(result.get("ok"), True)
        args = captured["args"]
        self.assertIn("--assignment-id", args)
        self.assertIn("HW_1", args)
        self.assertIn("--kp", args)
        self.assertIn("力学", args)
        self.assertIn("--generate", args)
        self.assertIn("assignment.meta.postprocess_failed", [item[0] for item in captured["log"]])

    def test_generate_http_defaults_generate_true_for_problem_set_ai(self):
        import inspect

        from fastapi import APIRouter
        from fastapi.routing import APIRoute

        from services.api.routes.assignment_generation_routes import (
            register_assignment_generation_routes,
        )

        class _App:
            async def post_generate_assignment(self, **kwargs):
                return kwargs

        router = APIRouter()
        register_assignment_generation_routes(router, app_deps=None, assignment_app=_App())
        route = next(
            item
            for item in router.routes
            if isinstance(item, APIRoute) and item.path == "/assignment/generate"
        )
        param = inspect.signature(route.endpoint).parameters["generate"]
        default = getattr(param.default, "default", param.default)
        self.assertIs(default, True)

    def test_generate_omitted_kind_defaults_problem_set(self):
        deps, captured = self._deps()
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        try:
            result = generate_assignment(
                assignment_id="HW_1",
                kp="力学",
                question_ids="",
                per_kp=1,
                core_examples="",
                generate=True,
                mode="kp",
                date="2026-02-08",
                due_at="",
                class_name="",
                student_ids="",
                source="teacher",
                requirements_json=None,
                subject_id="physics",
                deps=deps,
            )
        finally:
            reset_current_principal(token)
        self.assertTrue(result.get("ok"))
        self.assertIn("--generate", captured["args"])
        self.assertEqual(captured["log"][0][0], "assignment.kind.defaulted")

    def test_scenario_ai_draft_calls_llm_for_brief(self):
        from unittest.mock import patch

        deps, captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{**deps.__dict__, "app_root": Path(__file__).resolve().parent.parent}
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            from pathlib import Path as _P

            data_dir = _P(td) / "data"
            with patch("services.api.paths.DATA_DIR", data_dir), patch(
                "llm_gateway.LLMGateway"
            ) as gateway_cls:
                gateway_cls.return_value.generate.return_value.text = json.dumps(
                    {
                        "brief": "学生在操场观察摆动。",
                        "discussion_goals": ["描述现象"],
                        "rubric": "记录步骤",
                    },
                    ensure_ascii=False,
                )
                try:
                    result = generate_assignment(
                        assignment_id="HW_SCEN",
                        kp="",
                        question_ids="",
                        per_kp=5,
                        core_examples="",
                        generate=True,
                        mode="",
                        date="2026-02-08",
                        due_at="",
                        class_name="",
                        student_ids="",
                        source="teacher",
                        requirements_json=json.dumps(
                            {"subject": "科学", "topic": "摆", "grade_level": "初二"},
                            ensure_ascii=False,
                        ),
                        subject_id="generic",
                        assignment_kind="scenario",
                        deps=deps,
                    )
                finally:
                    reset_current_principal(token)
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("draft", {}).get("assignment_kind"), "scenario")
            self.assertIn("学生在操场观察摆动", result.get("draft", {}).get("requirements", {}).get("brief", ""))
            self.assertIsNone(captured["args"])
            gateway_cls.assert_called()

    def test_scenario_ai_draft_has_brief_not_generated_stems(self):
        from unittest.mock import patch

        deps, _captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{**deps.__dict__, "app_root": Path(__file__).resolve().parent.parent}
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            from pathlib import Path as _P

            data_dir = _P(td) / "data"
            with patch("services.api.paths.DATA_DIR", data_dir), patch(
                "llm_gateway.LLMGateway"
            ) as gateway_cls:
                gateway_cls.return_value.generate.return_value.text = (
                    '{"brief":"情景 brief","discussion_goals":["g1"]}'
                )
                try:
                    generate_assignment(
                        assignment_id="HW_SCEN2",
                        kp="",
                        question_ids="",
                        per_kp=5,
                        core_examples="",
                        generate=True,
                        mode="",
                        date="2026-02-08",
                        due_at="",
                        class_name="",
                        student_ids="",
                        source="teacher",
                        requirements_json='{"subject":"科学","topic":"史","grade_level":"初二"}',
                        subject_id="generic",
                        assignment_kind="scenario",
                        deps=deps,
                    )
                finally:
                    reset_current_principal(token)
            folder = data_dir / "assignments" / "HW_SCEN2"
            self.assertTrue((folder / "brief.md").exists())
            self.assertFalse((folder / "generated_stems").exists())
            csv_text = (folder / "questions.csv").read_text(encoding="utf-8")
            self.assertEqual(len([line for line in csv_text.splitlines() if line.strip()]) , 1)

    def test_non_problem_set_generate_ignores_generate_flag(self):
        from unittest.mock import patch

        deps, captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{**deps.__dict__, "app_root": Path(__file__).resolve().parent.parent}
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            from pathlib import Path as _P

            data_dir = _P(td) / "data"
            with patch("services.api.paths.DATA_DIR", data_dir), patch(
                "llm_gateway.LLMGateway"
            ) as gateway_cls:
                gateway_cls.return_value.generate.return_value.text = '{"brief":"实践 brief"}'
                try:
                    generate_assignment(
                        assignment_id="HW_PRAC",
                        kp="",
                        question_ids="",
                        per_kp=5,
                        core_examples="",
                        generate=True,
                        mode="",
                        date="2026-02-08",
                        due_at="",
                        class_name="",
                        student_ids="",
                        source="teacher",
                        requirements_json='{"subject":"科学","topic":"实验","grade_level":"初二"}',
                        subject_id="generic",
                        assignment_kind="practical",
                        deps=deps,
                    )
                finally:
                    reset_current_principal(token)
        self.assertIsNone(captured["args"])

    def test_generate_returns_folder_questions_and_missing(self):
        from unittest.mock import patch

        deps, _captured = self._deps()
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            data_dir = Path(td) / "data"
            folder = data_dir / "assignments" / "HW_1"
            folder.mkdir(parents=True)
            (folder / "questions.csv").write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n"
                "Q9,力学,basic,open,,,,\n",
                encoding="utf-8",
            )
            (folder / "requirements.json").write_text(
                json.dumps({"subject": "物理"}, ensure_ascii=False),
                encoding="utf-8",
            )
            with patch("services.api.paths.DATA_DIR", data_dir):
                try:
                    result = generate_assignment(
                        assignment_id="HW_1",
                        kp="力学",
                        question_ids="",
                        per_kp=1,
                        core_examples="",
                        generate=True,
                        mode="kp",
                        date="2026-02-08",
                        due_at="",
                        class_name="",
                        student_ids="",
                        source="teacher",
                        requirements_json=None,
                        subject_id="physics",
                        skip_validation=True,
                        deps=deps,
                    )
                finally:
                    reset_current_principal(token)
        draft = result.get("draft") or {}
        self.assertEqual(draft.get("questions", [{}])[0].get("question_id"), "Q9")
        self.assertEqual(draft.get("requirements", {}).get("subject"), "物理")
        self.assertIn("topic", draft.get("requirements_missing") or [])
        self.assertEqual(draft.get("assignment_kind"), "problem_set")
        self.assertEqual(draft.get("content_source"), "ai")
        self.assertNotIn("job_id", draft)

    def test_generate_rejects_unsafe_assignment_id(self):
        deps, _captured = self._deps()
        for aid in (".", "../escape", "a/b"):
            with self.assertRaises(AssignmentGenerateError) as cm:
                generate_assignment(
                    assignment_id=aid,
                    kp="",
                    question_ids="",
                    per_kp=5,
                    core_examples="",
                    generate=True,
                    mode="",
                    date="2026-02-08",
                    due_at="",
                    class_name="",
                    student_ids="",
                    source="teacher",
                    requirements_json=None,
                    deps=deps,
                )
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "invalid assignment_id")

    def test_scenario_generate_conflict_on_published(self):
        from unittest.mock import patch

        deps, _captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{**deps.__dict__, "app_root": Path(__file__).resolve().parent.parent}
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            data_dir = Path(td) / "data"
            folder = data_dir / "assignments" / "HW_PUB"
            folder.mkdir(parents=True)
            (folder / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_PUB",
                        "teacher_id": "t_zhang",
                        "visibility_status": "published",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("services.api.paths.DATA_DIR", data_dir), patch(
                "llm_gateway.LLMGateway"
            ) as gateway_cls:
                try:
                    with self.assertRaises(AssignmentGenerateError) as cm:
                        generate_assignment(
                            assignment_id="HW_PUB",
                            kp="",
                            question_ids="",
                            per_kp=5,
                            core_examples="",
                            generate=True,
                            mode="",
                            date="2026-02-08",
                            due_at="",
                            class_name="",
                            student_ids="",
                            source="teacher",
                            requirements_json='{"subject":"科学","topic":"摆","grade_level":"初二"}',
                            subject_id="generic",
                            assignment_kind="scenario",
                            skip_validation=True,
                            deps=deps,
                        )
                finally:
                    reset_current_principal(token)
            self.assertEqual(cm.exception.status_code, 409)
            self.assertEqual(cm.exception.detail, "assignment already exists")
            gateway_cls.assert_not_called()
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta.get("visibility_status"), "published")

    def test_generate_failed_leaves_visibility_unchanged(self):
        from unittest.mock import patch

        deps, _captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{**deps.__dict__, "app_root": Path(__file__).resolve().parent.parent}
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            data_dir = Path(td) / "data"
            folder = data_dir / "assignments" / "HW_FAIL"
            folder.mkdir(parents=True)
            (folder / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_FAIL",
                        "teacher_id": "t_zhang",
                        "visibility_status": "draft",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("services.api.paths.DATA_DIR", data_dir), patch(
                "llm_gateway.LLMGateway"
            ) as gateway_cls:
                gateway_cls.return_value.generate.return_value.text = "not-json"
                try:
                    with self.assertRaises(AssignmentGenerateError) as cm:
                        generate_assignment(
                            assignment_id="HW_FAIL",
                            kp="",
                            question_ids="",
                            per_kp=5,
                            core_examples="",
                            generate=True,
                            mode="",
                            date="2026-02-08",
                            due_at="",
                            class_name="",
                            student_ids="",
                            source="teacher",
                            requirements_json='{"subject":"科学","topic":"摆","grade_level":"初二"}',
                            subject_id="generic",
                            assignment_kind="scenario",
                            skip_validation=True,
                            deps=deps,
                        )
                finally:
                    reset_current_principal(token)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "generate_failed")
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta.get("visibility_status"), "draft")
            self.assertFalse((folder / "brief.md").exists())

    def test_generate_failed_empty_brief_leaves_visibility_unchanged(self):
        from unittest.mock import patch

        deps, _captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{**deps.__dict__, "app_root": Path(__file__).resolve().parent.parent}
        )
        token = set_current_principal(AuthPrincipal(actor_id="t_zhang", role="teacher"))
        with TemporaryDirectory() as td:
            data_dir = Path(td) / "data"
            folder = data_dir / "assignments" / "HW_EMPTY"
            folder.mkdir(parents=True)
            (folder / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_EMPTY",
                        "teacher_id": "t_zhang",
                        "visibility_status": "draft",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("services.api.paths.DATA_DIR", data_dir), patch(
                "llm_gateway.LLMGateway"
            ) as gateway_cls:
                gateway_cls.return_value.generate.return_value.text = '{"brief":""}'
                try:
                    with self.assertRaises(AssignmentGenerateError) as cm:
                        generate_assignment(
                            assignment_id="HW_EMPTY",
                            kp="",
                            question_ids="",
                            per_kp=5,
                            core_examples="",
                            generate=True,
                            mode="",
                            date="2026-02-08",
                            due_at="",
                            class_name="",
                            student_ids="",
                            source="teacher",
                            requirements_json='{"subject":"科学","topic":"摆","grade_level":"初二"}',
                            subject_id="generic",
                            assignment_kind="scenario",
                            skip_validation=True,
                            deps=deps,
                        )
                finally:
                    reset_current_principal(token)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "generate_failed")
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta.get("visibility_status"), "draft")


if __name__ == "__main__":
    unittest.main()
