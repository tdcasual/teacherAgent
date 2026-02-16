from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ChatStreamStabilitySmokeScriptTest(unittest.TestCase):
    def test_script_generates_report_and_meets_stability_checks(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "chat_stream_stability_smoke.py"
        self.assertTrue(script.exists(), f"script not found: {script}")

        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "report.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--jobs",
                    "32",
                    "--events-per-job",
                    "5",
                    "--writers",
                    "8",
                    "--signal-cap",
                    "16",
                    "--signal-ttl-sec",
                    "0.05",
                    "--report",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertTrue(report_path.exists(), "report was not generated")
            payload = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertEqual(int(payload.get("jobs") or 0), 32)
            self.assertEqual(int(payload.get("events_per_job") or 0), 5)
            self.assertEqual(int(payload.get("load_mismatch_jobs") or 0), 0)
            self.assertLessEqual(
                int(payload.get("signal_entries_after_capacity_wave") or 0),
                int(payload.get("signal_cap") or 0),
            )
            self.assertLessEqual(int(payload.get("signal_entries_after_ttl_cleanup") or 0), 4)


if __name__ == "__main__":
    unittest.main()
