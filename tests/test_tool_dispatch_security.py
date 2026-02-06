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
            res = app_mod.tool_dispatch(
                "lesson.capture",
                {"lesson_id": "L1", "topic": "T", "sources": ["/etc/passwd"]},
                role="teacher",
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "source_not_found_or_outside_app_root")

    def test_core_example_render_rejects_outside_out_path(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.tool_dispatch(
                "core_example.render",
                {"example_id": "CE001", "out": "/etc/out.pdf"},
                role="teacher",
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "out_outside_app_root")

    def test_core_example_register_rejects_outside_files(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            res = app_mod.tool_dispatch(
                "core_example.register",
                {"example_id": "CE001", "kp_id": "KP-M01", "core_model": "M", "stem_file": "/etc/passwd"},
                role="teacher",
            )
            self.assertIn("error", res)
            self.assertEqual(res["error"], "stem_file_not_found_or_outside_app_root")

    def test_teacher_llm_routing_tool_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.tool_dispatch("teacher.llm_routing.get", {}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

            allowed = app_mod.tool_dispatch("teacher.llm_routing.get", {}, role="teacher")
            self.assertTrue(allowed.get("ok"))
            self.assertIn("routing", allowed)

    def test_chart_exec_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.tool_dispatch("chart.exec", {"python_code": "print('hi')"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_chart_agent_run_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.tool_dispatch("chart.agent.run", {"task": "plot"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")

    def test_exam_analysis_charts_generate_requires_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            denied = app_mod.tool_dispatch("exam.analysis.charts.generate", {"exam_id": "EX001"}, role="student")
            self.assertIn("error", denied)
            self.assertEqual(denied["error"], "permission denied")


if __name__ == "__main__":
    unittest.main()
