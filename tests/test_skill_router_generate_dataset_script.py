import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


class SkillRouterGenerateDatasetScriptTest(unittest.TestCase):
    def test_script_generates_requested_row_count(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "skill_router_generate_dataset.py"
        self.assertTrue(script.exists(), f"script not found: {script}")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out_path = tmp / "generated.jsonl"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--output",
                    str(out_path),
                    "--size",
                    "40",
                    "--seed",
                    "7",
                    "--mix",
                    "golden,fuzz,adversarial,drift",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertTrue(out_path.exists(), "dataset not generated")
            lines = [x for x in out_path.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(lines), 40)
            sample = json.loads(lines[0])
            self.assertIn("role", sample)
            self.assertIn("text", sample)
            self.assertIn("expected_skill_id", sample)
            self.assertIn("bucket", sample)


if __name__ == "__main__":
    unittest.main()
