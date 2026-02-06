import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class OpencodeExecutorTest(unittest.TestCase):
    def test_status_from_config_file(self):
        from services.api.opencode_executor import resolve_opencode_status

        with TemporaryDirectory() as td:
            root = Path(td)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "opencode_bridge.yaml").write_text(
                "enabled: true\nbin: /bin/echo\nmode: run\n",
                encoding="utf-8",
            )
            status = resolve_opencode_status(root)
            self.assertTrue(status.get("enabled"))
            self.assertTrue(status.get("available"))
            self.assertEqual(status.get("reason"), "ok")

    def test_run_codegen_parses_json_output(self):
        import services.api.opencode_executor as mod
        from services.api.opencode_executor import run_opencode_codegen

        with TemporaryDirectory() as td:
            mod._HELP_CACHE.clear()  # type: ignore[attr-defined]
            root = Path(td)
            run_help_output = "--format\n--agent\n--model\n--config\n--attach\n--prompt\n"
            payload = {
                "python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2],[2,3])\nsave_chart()",
                "packages": ["pandas"],
                "summary": "ok",
            }
            line = json.dumps(payload, ensure_ascii=False)

            class _Proc:
                def __init__(self, returncode=0, stdout="", stderr=""):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            with patch("services.api.opencode_executor.subprocess.run") as mock_run:
                mock_run.side_effect = [
                    _Proc(returncode=0, stdout=run_help_output, stderr=""),
                    _Proc(returncode=0, stdout=line + "\n", stderr=""),
                ]
                result = run_opencode_codegen(
                    app_root=root,
                    task="画图",
                    input_data={"a": 1},
                    last_error="",
                    previous_code="",
                    attempt=1,
                    max_retries=3,
                    overrides={"enabled": True, "bin": "/bin/echo"},
                )

            self.assertTrue(result.get("ok"))
            self.assertIn("save_chart", str(result.get("python_code") or ""))
            self.assertIn("pandas", result.get("packages") or [])

    def test_run_codegen_parses_json_event_part_text(self):
        import services.api.opencode_executor as mod
        from services.api.opencode_executor import run_opencode_codegen

        with TemporaryDirectory() as td:
            mod._HELP_CACHE.clear()  # type: ignore[attr-defined]
            root = Path(td)
            run_help_output = "--format\n--agent\n--model\n--config\n--attach\n"
            content_payload = {
                "python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2],[2,3])\nsave_chart('main.png')",
                "packages": ["yfinance", "pandas"],
                "summary": "ok",
            }
            event_line = json.dumps(
                {
                    "type": "text",
                    "part": {
                        "type": "text",
                        "text": json.dumps(content_payload, ensure_ascii=False),
                    },
                },
                ensure_ascii=False,
            )

            class _Proc:
                def __init__(self, returncode=0, stdout="", stderr=""):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            with patch("services.api.opencode_executor.subprocess.run") as mock_run:
                mock_run.side_effect = [
                    _Proc(returncode=0, stdout=run_help_output, stderr=""),
                    _Proc(returncode=0, stdout=event_line + "\n", stderr=""),
                ]
                result = run_opencode_codegen(
                    app_root=root,
                    task="画图",
                    input_data={"a": 1},
                    last_error="",
                    previous_code="",
                    attempt=1,
                    max_retries=3,
                    overrides={"enabled": True, "bin": "/bin/echo"},
                )

            self.assertTrue(result.get("ok"))
            self.assertIn("save_chart", str(result.get("python_code") or ""))
            self.assertIn("yfinance", result.get("packages") or [])


if __name__ == "__main__":
    unittest.main()
