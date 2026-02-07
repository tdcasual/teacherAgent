import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
