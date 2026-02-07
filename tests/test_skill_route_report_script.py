import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


class SkillRouteReportScriptTest(unittest.TestCase):
    def test_script_summarizes_skill_resolve_events(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "skill_route_report.py"
        self.assertTrue(script.exists(), f"script not found: {script}")

        rows = [
            {
                "ts": "2026-02-07T10:00:00",
                "event": "skill.resolve",
                "role": "teacher",
                "requested_skill_id": "",
                "effective_skill_id": "physics-homework-generator",
                "reason": "auto_rule",
                "confidence": 0.84,
            },
            {
                "ts": "2026-02-07T10:00:03",
                "event": "skill.resolve",
                "role": "teacher",
                "requested_skill_id": "",
                "effective_skill_id": "physics-teacher-ops",
                "reason": "role_default",
                "confidence": 0.28,
            },
            {
                "ts": "2026-02-07T10:00:06",
                "event": "skill.resolve",
                "role": "teacher",
                "requested_skill_id": "physics-core-examples",
                "effective_skill_id": "physics-core-examples",
                "reason": "explicit",
                "confidence": 1.0,
            },
        ]
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "diagnostics.log"
            log_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--log", str(log_path), "--format", "json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout or "{}")
            self.assertEqual(payload.get("total"), 3)
            self.assertEqual((payload.get("reasons") or {}).get("explicit"), 1)
            self.assertEqual((payload.get("effective_skills") or {}).get("physics-homework-generator"), 1)
            self.assertIn("(empty) -> physics-homework-generator", payload.get("transitions") or {})
            self.assertAlmostEqual(float(payload.get("auto_hit_rate") or 0.0), 1 / 3, places=3)


if __name__ == "__main__":
    unittest.main()
