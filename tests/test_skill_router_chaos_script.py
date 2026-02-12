import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SkillRouterChaosScriptTest(unittest.TestCase):
    def test_script_runs_small_p0_suite_without_crashing(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "skill_router_chaos.py"
        self.assertTrue(script.exists(), f"script not found: {script}")

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            report_path = tmp / "chaos_report.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--app-root",
                    str(repo_root),
                    "--rounds",
                    "8",
                    "--workers",
                    "4",
                    "--suite",
                    "p0",
                    "--report",
                    str(report_path),
                    "--assert-no-crash",
                    "--assert-fallback-valid",
                    "--assert-load-errors-visible",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertTrue(report_path.exists(), "chaos report not generated")
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(payload.get("total_cases") or 0), 8)
            self.assertEqual(int(payload.get("crashes") or 0), 0)
            self.assertIn("by_scenario", payload)

    def test_missing_yaml_expectation_depends_on_skill_md_fallback(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "skill_router_chaos.py"
        spec = importlib.util.spec_from_file_location("skill_router_chaos_module", script)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            skill_with_md = root / "with_md"
            skill_with_md.mkdir(parents=True, exist_ok=True)
            (skill_with_md / "skill.yaml").write_text("id: with_md\n", encoding="utf-8")
            (skill_with_md / "SKILL.md").write_text("# with_md\n", encoding="utf-8")

            skill_without_md = root / "without_md"
            skill_without_md.mkdir(parents=True, exist_ok=True)
            (skill_without_md / "skill.yaml").write_text("id: without_md\n", encoding="utf-8")

            with patch.object(mod, "_pick_skill_yaml", return_value=skill_with_md / "skill.yaml"):
                meta_with_md = mod._scenario_missing_yaml(root, random.Random(0))
            self.assertEqual(meta_with_md.get("scenario"), "missing_yaml")
            self.assertFalse(bool(meta_with_md.get("expect_load_error")))
            self.assertFalse((skill_with_md / "skill.yaml").exists())

            with patch.object(
                mod, "_pick_skill_yaml", return_value=skill_without_md / "skill.yaml"
            ):
                meta_without_md = mod._scenario_missing_yaml(root, random.Random(1))
            self.assertEqual(meta_without_md.get("scenario"), "missing_yaml")
            self.assertTrue(bool(meta_without_md.get("expect_load_error")))
            self.assertFalse((skill_without_md / "skill.yaml").exists())


if __name__ == "__main__":
    unittest.main()
