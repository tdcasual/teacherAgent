import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


class SkillRouterStressEvalScriptTest(unittest.TestCase):
    def test_script_generates_report_and_passes_reasonable_gates(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "skill_router_stress_eval.py"
        self.assertTrue(script.exists(), f"script not found: {script}")

        rows = [
            {
                "id": "g001",
                "role": "teacher",
                "requested_skill_id": "",
                "text": "请生成作业，作业ID A2403_2026-02-04，每个知识点 5 题",
                "expected_skill_id": "physics-homework-generator",
                "bucket": "golden",
            },
            {
                "id": "g002",
                "role": "teacher",
                "requested_skill_id": "",
                "text": "先读取当前模型路由配置，再回滚到版本 3",
                "expected_skill_id": "physics-llm-routing",
                "bucket": "golden",
            },
            {
                "id": "g003",
                "role": "student",
                "requested_skill_id": "",
                "text": "开始今天作业",
                "expected_skill_id": "physics-student-coach",
                "bucket": "golden",
            },
        ]

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            dataset_path = tmp / "dataset.jsonl"
            report_path = tmp / "report.json"
            dataset_path.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in rows),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--app-root",
                    str(repo_root),
                    "--dataset",
                    str(dataset_path),
                    "--report",
                    str(report_path),
                    "--workers",
                    "4",
                    "--gate-top1",
                    "0.80",
                    "--gate-default",
                    "0.50",
                    "--gate-ambiguous",
                    "0.50",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertTrue(report_path.exists(), "report was not generated")
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("total") or 0), 3)
            self.assertGreaterEqual(float(payload.get("top1_rate") or 0.0), 0.80)
            self.assertIn("confusion_matrix", payload)

    def test_script_fails_when_gate_is_too_strict(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "skill_router_stress_eval.py"
        self.assertTrue(script.exists(), f"script not found: {script}")

        repo_root = Path(__file__).resolve().parents[1]
        rows = [
            {
                "id": "s001",
                "role": "teacher",
                "requested_skill_id": "",
                "text": "请帮我生成作业",
                "expected_skill_id": "physics-homework-generator",
                "bucket": "golden",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            dataset_path = tmp / "dataset.jsonl"
            report_path = tmp / "report.json"
            dataset_path.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in rows),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--app-root",
                    str(repo_root),
                    "--dataset",
                    str(dataset_path),
                    "--report",
                    str(report_path),
                    "--gate-top1",
                    "1.01",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0, "strict gate should fail")


if __name__ == "__main__":
    unittest.main()
