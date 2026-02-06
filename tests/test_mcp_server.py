import csv
import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_mcp(tmp_dir: Path, api_key: str = ""):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["MCP_API_KEY"] = api_key
    os.environ["MCP_SCRIPT_TIMEOUT_SEC"] = "5"
    import services.mcp.app as mcp_mod

    importlib.reload(mcp_mod)
    return mcp_mod


class MCPServerTest(unittest.TestCase):
    def test_tools_list_and_basic_calls(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            mcp_mod = load_mcp(tmp, api_key="test_key")

            data_dir = Path(os.environ["DATA_DIR"])
            (data_dir / "student_profiles").mkdir(parents=True, exist_ok=True)
            (data_dir / "student_profiles" / "C1_A.json").write_text(
                json.dumps({"student_id": "C1_A", "student_name": "A", "class_name": "C1"}, ensure_ascii=False),
                encoding="utf-8",
            )

            # Minimal exam setup.
            exam_id = "EX_TEST"
            exam_dir = data_dir / "exams" / exam_id
            derived_dir = exam_dir / "derived"
            derived_dir.mkdir(parents=True, exist_ok=True)
            responses_path = derived_dir / "responses_scored.csv"
            questions_path = derived_dir / "questions.csv"

            with responses_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "exam_id",
                        "student_id",
                        "student_name",
                        "class_name",
                        "question_id",
                        "question_no",
                        "sub_no",
                        "raw_label",
                        "raw_value",
                        "raw_answer",
                        "score",
                        "is_correct",
                    ]
                )
                writer.writerow([exam_id, "C1_A", "A", "C1", "Q1", "1", "", "1", "4", "", "4", "1"])
                writer.writerow([exam_id, "C1_B", "B", "C1", "Q1", "1", "", "1", "0", "", "0", "0"])

            with questions_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
                writer.writerow(["Q1", "1", "", "1", "4", ""])

            analysis_dir = data_dir / "analysis" / exam_id
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "draft.json").write_text(
                json.dumps({"exam_id": exam_id, "generated_at": "2026-02-05T00:00:00", "totals": {}}, ensure_ascii=False),
                encoding="utf-8",
            )

            manifest = {
                "exam_id": exam_id,
                "generated_at": "2026-02-05T00:00:00",
                "files": {"responses_scored": str(responses_path.resolve()), "questions": str(questions_path.resolve())},
                "counts": {"students": 2, "responses": 2, "questions": 1},
            }
            (exam_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            headers = {"X-API-Key": "test_key"}
            client = TestClient(mcp_mod.app)

            res = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertIn("result", payload)
            names = {t.get("name") for t in payload["result"]}
            self.assertIn("student.profile.get", names)
            self.assertIn("exam.get", names)
            self.assertIn("assignment.generate", names)

            res = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "student.profile.get", "arguments": {"student_id": "C1_A"}},
                },
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["result"]["student_id"], "C1_A")

            res = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "exam.get", "arguments": {"exam_id": exam_id}},
                },
            )
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json()["result"]["ok"])
            self.assertEqual(res.json()["result"]["counts"]["students"], 2)

            res = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "exam.students.list", "arguments": {"exam_id": exam_id, "limit": 10}},
                },
            )
            self.assertEqual(res.status_code, 200)
            students = res.json()["result"]["students"]
            self.assertEqual(len(students), 2)
            self.assertEqual(students[0]["rank"], 1)

    def test_auth_enforced_when_configured(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            mcp_mod = load_mcp(tmp, api_key="secret")
            client = TestClient(mcp_mod.app)
            res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()

