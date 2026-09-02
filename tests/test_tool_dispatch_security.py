import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class ToolDispatchSecurityTest(unittest.TestCase):
    def test_lesson_capture_rejects_outside_paths(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.get_core().tool_dispatch(
                "lesson.capture",
                {"lesson_id": "L1", "topic": "T", "sources": ["/etc/passwd"]},
                role="teacher",
                confirmed=True,
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "source_not_found_or_outside_app_root")

    def test_core_example_render_rejects_outside_out_path(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.get_core().tool_dispatch(
                "core_example.render",
                {"example_id": "CE001", "out": "/etc/out.pdf"},
                role="teacher",
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "out_outside_app_root")

    def test_core_example_register_rejects_outside_files(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.get_core().tool_dispatch(
                "core_example.register",
                {"example_id": "CE001", "kp_id": "KP-M01", "core_model": "M", "stem_file": "/etc/passwd"},
                role="teacher",
                confirmed=True,
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "stem_file_not_found_or_outside_app_root")

    def test_removed_teacher_llm_routing_tool_is_unknown(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            result = app_mod.get_core().tool_dispatch("teacher.llm_routing.get", {}, role="teacher")
            self.assertIn("error", result)
            self.assertEqual(result["error"], "unknown tool: teacher.llm_routing.get")

    def test_chart_exec_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.get_core().tool_dispatch("chart.exec", {"python_code": "print('hi')"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_chart_agent_run_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.get_core().tool_dispatch("chart.agent.run", {"task": "plot"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_chart_agent_run_rejects_opencode_engine_for_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            result = app_mod.get_core().tool_dispatch("chart.agent.run", {"task": "plot", "engine": "opencode"}, role="teacher", confirmed=True)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "opencode_forbidden")
            self.assertEqual(result.get("status_code"), 400)

    def test_assignment_generate_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.get_core().tool_dispatch(
                "assignment.generate",
                {"assignment_id": "HW1", "subject_id": "physics"},
                role="student",
            )
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_assignment_generate_forbids_other_teacher_existing_assignment(self):
        from services.api.tool_dispatch_service import ToolDispatchDeps, tool_dispatch

        class _Registry:
            def get(self, name):
                return name if name == "assignment.generate" else None

            def validate_arguments(self, _name, _args):
                return []

        generated = {}

        def _deps():
            return ToolDispatchDeps(
                tool_registry=_Registry(),
                list_assignments=lambda owner_teacher_id=None: {},
                list_lessons=lambda: {},
                lesson_capture=lambda args: {},
                student_search=lambda query, limit: {},
                student_profile_get=lambda student_id: {},
                student_profile_update=lambda args: {},
                student_import=lambda args: {},
                assignment_generate=lambda args: generated.__setitem__("ok", True) or {"ok": True},
                assignment_render=lambda args: {},
                save_assignment_requirements=lambda *a, **k: {},
                parse_date_str=lambda raw: str(raw or ""),
                core_example_search=lambda args: {},
                core_example_register=lambda args: {},
                core_example_render=lambda args: {},
                chart_agent_run=lambda args: {},
                chart_exec=lambda args: {},
                resolve_teacher_id=lambda raw: str(raw or ""),
                ensure_teacher_workspace=lambda teacher_id: Path("/tmp") / str(teacher_id),
                teacher_workspace_dir=lambda teacher_id: Path("/tmp") / str(teacher_id),
                teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / str(teacher_id) / name,
                teacher_daily_memory_path=lambda teacher_id, date_str=None: Path("/tmp") / str(teacher_id) / "d.md",
                teacher_read_text=lambda path, max_chars=8000: "",
                teacher_memory_search=lambda teacher_id, query, limit=5: {},
                teacher_memory_propose=lambda *a, **k: {},
                teacher_memory_apply=lambda *a, **k: {},
                assignment_owner_id=lambda assignment_id: "t_owner" if assignment_id == "HW_A" else None,
            )

        stolen = tool_dispatch(
            "assignment.generate",
            {"assignment_id": "HW_A", "subject_id": "physics"},
            role="teacher",
            teacher_id="t_thief",
            deps=_deps(),
            confirmed=True,
        )
        self.assertEqual(stolen.get("error"), "forbidden_assignment_owner")
        self.assertNotIn("ok", generated)

        created = tool_dispatch(
            "assignment.generate",
            {"assignment_id": "HW_NEW", "subject_id": "physics"},
            role="teacher",
            teacher_id="t_thief",
            deps=_deps(),
            confirmed=True,
        )
        self.assertTrue(created.get("ok"))


if __name__ == "__main__":
    unittest.main()
