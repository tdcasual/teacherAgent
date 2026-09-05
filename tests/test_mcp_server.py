import csv
import importlib
import inspect
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


UNBOUND_TOOL_NAMES = {"student.search", "student.profile.get"}
BOUND_EXTRA_TOOL_NAMES = {"student.profile.update", "assignment.list", "assignment.render"}
BOUND_TOOL_NAMES = UNBOUND_TOOL_NAMES | BOUND_EXTRA_TOOL_NAMES
FORBIDDEN_TOOL_PREFIXES = ("lesson.", "core_example.", "exam.")


def load_mcp(tmp_dir: Path, api_key: str = "test-key", bound_teacher_id: str = ""):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["MCP_API_KEY"] = api_key
    os.environ["MCP_SCRIPT_TIMEOUT_SEC"] = "5"
    if bound_teacher_id:
        os.environ["MCP_BOUND_TEACHER_ID"] = bound_teacher_id
    else:
        os.environ.pop("MCP_BOUND_TEACHER_ID", None)
    import services.mcp.app as mcp_mod

    importlib.reload(mcp_mod)
    return mcp_mod


def _tool_names(client: TestClient, api_key: str) -> set:
    res = client.post(
        "/mcp",
        headers={"X-API-Key": api_key},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert res.status_code == 200
    payload = res.json()
    assert "result" in payload
    return {t.get("name") for t in payload["result"]}


def _call_tool(client: TestClient, api_key: str, name: str, arguments: dict, rpc_id: int = 1):
    return client.post(
        "/mcp",
        headers={"X-API-Key": api_key},
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def _seed_assignment(data_dir: Path, assignment_id: str, teacher_id: str) -> None:
    folder = data_dir / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(
        json.dumps({"assignment_id": assignment_id, "teacher_id": teacher_id}, ensure_ascii=False),
        encoding="utf-8",
    )


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

    def test_load_mcp_default_api_key_is_test_key(self):
        self.assertEqual(inspect.signature(load_mcp).parameters["api_key"].default, "test-key")
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td))
            client = TestClient(mcp_mod.app)
            missing = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            self.assertEqual(missing.status_code, 401)
            ok = client.post(
                "/mcp",
                headers={"X-API-Key": "test-key"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            self.assertEqual(ok.status_code, 200)
            self.assertIn("result", ok.json())

    def test_mcp_empty_api_key_rejects_rpc(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="")
            client = TestClient(mcp_mod.app)
            res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            self.assertEqual(res.status_code, 503)
            self.assertEqual(res.json()["detail"], "mcp_auth_not_configured")
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")

    def test_mcp_missing_header_is_401(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="secret")
            client = TestClient(mcp_mod.app)
            res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json()["detail"], "Unauthorized")
            self.assertNotEqual(res.status_code, 500)

    def test_mcp_wrong_key_401(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="secret")
            client = TestClient(mcp_mod.app)
            wrong = client.post(
                "/mcp",
                headers={"X-API-Key": "nope"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            self.assertEqual(wrong.status_code, 401)
            self.assertEqual(wrong.json()["detail"], "Unauthorized")
            ok = client.post(
                "/mcp",
                headers={"X-API-Key": "secret"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            self.assertEqual(ok.status_code, 200)
            self.assertIn("result", ok.json())

    def test_unbound_tools_list_is_student_read_only(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="secret")
            names = _tool_names(TestClient(mcp_mod.app), "secret")
            forbidden = {n for n in names if n.startswith(FORBIDDEN_TOOL_PREFIXES) or n == "assignment.generate"}
            self.assertEqual(forbidden, set())
            self.assertEqual(names, UNBOUND_TOOL_NAMES)

    def test_bound_tools_list_adds_only_student_update_and_assignment_io(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="secret", bound_teacher_id="t_bound")
            names = _tool_names(TestClient(mcp_mod.app), "secret")
            forbidden = {n for n in names if n.startswith(FORBIDDEN_TOOL_PREFIXES) or n == "assignment.generate"}
            self.assertEqual(forbidden, set())
            self.assertEqual(names, BOUND_TOOL_NAMES)

    def test_assignment_list_unbound_returns_mcp_teacher_unbound(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="secret")
            res = _call_tool(TestClient(mcp_mod.app), "secret", "assignment.list", {})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json().get("result"), {"error": "mcp_teacher_unbound"})

    def test_assignment_render_unbound_jsonrpc_403_mcp_teacher_unbound(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="secret")
            res = _call_tool(
                TestClient(mcp_mod.app),
                "secret",
                "assignment.render",
                {"assignment_id": "A1"},
            )
            self.assertEqual(res.status_code, 200)
            err = res.json().get("error") or {}
            self.assertEqual(err.get("code"), 403)
            self.assertEqual(err.get("message"), "mcp_teacher_unbound")

    def test_assignment_render_owner_mismatch_forbidden(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            mcp_mod = load_mcp(tmp, api_key="secret", bound_teacher_id="t_bound")
            _seed_assignment(Path(os.environ["DATA_DIR"]), "HW_OTHER", "t_other")
            res = _call_tool(
                TestClient(mcp_mod.app),
                "secret",
                "assignment.render",
                {"assignment_id": "HW_OTHER"},
            )
            self.assertEqual(res.status_code, 200)
            err = res.json().get("error") or {}
            self.assertEqual(err.get("code"), 403)
            self.assertEqual(err.get("message"), "forbidden_assignment_owner")

    def test_assignment_list_bound_filters_owner(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            mcp_mod = load_mcp(tmp, api_key="secret", bound_teacher_id="t_bound")
            data_dir = Path(os.environ["DATA_DIR"])
            _seed_assignment(data_dir, "HW_MINE", "t_bound")
            _seed_assignment(data_dir, "HW_OTHER", "t_other")
            res = _call_tool(TestClient(mcp_mod.app), "secret", "assignment.list", {}, rpc_id=2)
            self.assertEqual(res.status_code, 200)
            names = res.json()["result"]["assignments"]
            self.assertEqual(names, ["HW_MINE"])


if __name__ == "__main__":
    unittest.main()

