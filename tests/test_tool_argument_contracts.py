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


class ToolArgumentContractsTest(unittest.TestCase):
    def test_registry_disallows_unknown_top_level_fields(self):
        from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

        for name in DEFAULT_TOOL_REGISTRY.names():
            schema = DEFAULT_TOOL_REGISTRY.require(name).parameters
            self.assertEqual(schema.get("type"), "object", f"{name}: top-level schema must be object")
            self.assertIs(schema.get("additionalProperties"), False, f"{name}: additionalProperties should be false")

    def test_api_tool_dispatch_rejects_unknown_and_missing_args(self):
        with TemporaryDirectory() as td:
            app_mod = load_api(Path(td))

            unknown = app_mod.tool_dispatch("exam.get", {"exam_id": "EX1", "unexpected": 1}, role="teacher")
            self.assertEqual(unknown.get("error"), "invalid_arguments")
            self.assertEqual(unknown.get("tool"), "exam.get")
            self.assertTrue(any("unexpected" in item for item in unknown.get("issues") or []))

            missing = app_mod.tool_dispatch("exam.get", {}, role="teacher")
            self.assertEqual(missing.get("error"), "invalid_arguments")
            self.assertEqual(missing.get("tool"), "exam.get")
            self.assertTrue(any("required" in item for item in missing.get("issues") or []))

    def test_mcp_rejects_invalid_arguments_before_execution(self):
        with TemporaryDirectory() as td:
            mcp_mod = load_mcp(Path(td), api_key="k")
            client = TestClient(mcp_mod.app)
            headers = {"X-API-Key": "k"}

            res = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "exam.get", "arguments": {"exam_id": "EX1", "unexpected": "x"}},
                },
            )
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertEqual(payload["error"]["code"], -32602)
            self.assertEqual(payload["error"]["message"], "invalid arguments")
            self.assertEqual(payload["error"]["data"]["tool"], "exam.get")
            self.assertTrue(any("unexpected" in item for item in payload["error"]["data"]["issues"]))


if __name__ == "__main__":
    unittest.main()
