import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_api(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def load_mcp(tmp_dir: Path, api_key: str = ""):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["MCP_API_KEY"] = api_key
    os.environ["MCP_SCRIPT_TIMEOUT_SEC"] = "5"
    import services.mcp.app as mcp_mod

    importlib.reload(mcp_mod)
    return mcp_mod


class ToolRegistrySyncTest(unittest.TestCase):
    def test_registry_covers_teacher_allowed_tools(self):
        from services.common.tool_registry import DEFAULT_TOOL_REGISTRY
        from services.api.app import allowed_tools

        missing = sorted(set(allowed_tools("teacher")) - set(DEFAULT_TOOL_REGISTRY.names()))
        self.assertEqual(missing, [])

    def test_openai_and_mcp_specs_share_same_schema(self):
        from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

        for name in (
            "exam.get",
            "exam.students.list",
            "exam.range.top_students",
            "exam.range.summary.batch",
            "exam.question.batch.get",
            "assignment.generate",
            "lesson.capture",
            "core_example.register",
            "student.profile.update",
        ):
            tool = DEFAULT_TOOL_REGISTRY.require(name)
            openai = tool.to_openai()
            mcp = tool.to_mcp()
            self.assertEqual(openai["function"]["parameters"], mcp["inputSchema"])

    def test_run_agent_tools_filtered_by_skill(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_api(tmp)

            captured = {}

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):
                captured["tool_names"] = [t.get("function", {}).get("name") for t in (tools or [])]
                return {"choices": [{"message": {"content": "ok"}}]}

            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]

            result = app_mod.run_agent(
                messages=[{"role": "user", "content": "hello"}],
                role_hint="teacher",
                skill_id="physics-core-examples",
            )
            self.assertEqual(result.get("reply"), "ok")
            self.assertEqual(
                set(captured.get("tool_names") or []),
                {"core_example.search", "core_example.register", "core_example.render", "chart.agent.run", "chart.exec"},
            )

    def test_run_agent_default_skill_keeps_teacher_tools(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_api(tmp)

            captured = {}

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):
                captured["tool_names"] = [t.get("function", {}).get("name") for t in (tools or [])]
                return {"choices": [{"message": {"content": "ok"}}]}

            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]

            result = app_mod.run_agent(
                messages=[{"role": "user", "content": "hello"}],
                role_hint="teacher",
                skill_id="physics-teacher-ops",
            )
            self.assertEqual(result.get("reply"), "ok")
            denied = {
                "teacher.llm_routing.get",
                "teacher.llm_routing.simulate",
                "teacher.llm_routing.propose",
                "teacher.llm_routing.apply",
                "teacher.llm_routing.rollback",
            }
            self.assertEqual(set(captured.get("tool_names") or []), set(app_mod.allowed_tools("teacher")) - denied)

    def test_mcp_tools_list_matches_registry(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            mcp_mod = load_mcp(tmp, api_key="k")
            client = TestClient(mcp_mod.app)

            res = client.post("/mcp", headers={"X-API-Key": "k"}, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            self.assertEqual(res.status_code, 200)
            returned = res.json()["result"]

            from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

            expected = DEFAULT_TOOL_REGISTRY.mcp_tools(mcp_mod.MCP_TOOL_NAMES)  # type: ignore[attr-defined]
            self.assertEqual(returned, expected)


if __name__ == "__main__":
    unittest.main()
