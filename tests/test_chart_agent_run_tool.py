import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class ChartAgentRunToolTest(unittest.TestCase):
    def test_chart_agent_run_success_first_try(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            captured = {}

            # Ensure tests do not depend on a local opencode binary or repo config.
            def fake_status(app_root, overrides=None):  # type: ignore[no-untyped-def]
                return {"enabled": True, "available": False, "reason": "binary_not_found", "config": {}}

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):  # type: ignore[no-untyped-def]
                payload = {
                    "python_code": "import matplotlib.pyplot as plt\nplt.figure(figsize=(4,3))\nplt.plot([1,2,3],[2,1,3])\nsave_chart('main.png')",
                    "packages": ["pandas"],
                    "summary": "ok",
                }
                return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                captured["args"] = args
                return {
                    "ok": True,
                    "run_id": "chr_test",
                    "image_url": "/charts/chr_test/main.png",
                    "meta_url": "/chart-runs/chr_test/meta",
                    "artifacts": [{"name": "main.png", "url": "/charts/chr_test/main.png", "size": 123}],
                    "installed_packages": args.get("packages") or [],
                    "python_executable": "python3",
                }

            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]
            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]
            app_mod.resolve_opencode_status = fake_status  # type: ignore[attr-defined]

            res = app_mod.tool_dispatch(
                "chart.agent.run",
                {"task": "画一个简单折线图", "input_data": {"a": 1}, "packages": ["numpy"], "auto_install": True},
                role="teacher",
            )
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("attempt_used"), 1)
            self.assertIn("/charts/chr_test/main.png", res.get("markdown", ""))
            exec_args = captured.get("args") or {}
            self.assertTrue(exec_args.get("auto_install"))
            self.assertIn("numpy", exec_args.get("packages") or [])
            self.assertIn("pandas", exec_args.get("packages") or [])

    def test_chart_agent_run_retries_after_failure(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            llm_calls = {"count": 0}
            exec_calls = {"count": 0}

            # Ensure tests do not depend on a local opencode binary or repo config.
            def fake_status(app_root, overrides=None):  # type: ignore[no-untyped-def]
                return {"enabled": True, "available": False, "reason": "binary_not_found", "config": {}}

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):  # type: ignore[no-untyped-def]
                llm_calls["count"] += 1
                if llm_calls["count"] == 1:
                    payload = {"python_code": "raise ValueError('boom')", "packages": [], "summary": "bad"}
                else:
                    payload = {"python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2],[2,3])\nsave_chart()", "packages": [], "summary": "fix"}
                return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                exec_calls["count"] += 1
                if exec_calls["count"] == 1:
                    return {
                        "ok": False,
                        "run_id": "chr_fail",
                        "exit_code": 1,
                        "stderr": "ValueError: boom",
                        "meta_url": "/chart-runs/chr_fail/meta",
                    }
                return {
                    "ok": True,
                    "run_id": "chr_ok",
                    "image_url": "/charts/chr_ok/main.png",
                    "meta_url": "/chart-runs/chr_ok/meta",
                    "artifacts": [{"name": "main.png", "url": "/charts/chr_ok/main.png", "size": 120}],
                    "installed_packages": [],
                    "python_executable": "python3",
                }

            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]
            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]
            app_mod.resolve_opencode_status = fake_status  # type: ignore[attr-defined]

            res = app_mod.tool_dispatch(
                "chart.agent.run",
                {"task": "画图", "max_retries": 3},
                role="teacher",
            )
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("attempt_used"), 2)
            self.assertEqual(len(res.get("attempts") or []), 2)

    def test_chart_agent_run_with_opencode_engine(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            captured = {}

            def fake_status(app_root, overrides=None):  # type: ignore[no-untyped-def]
                return {
                    "enabled": True,
                    "available": True,
                    "reason": "ok",
                    "binary": "/usr/local/bin/opencode",
                    "config": {"max_retries": 2},
                }

            def fake_opencode(**kwargs):  # type: ignore[no-untyped-def]
                return {
                    "ok": True,
                    "python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2,3],[2,4,3])\nsave_chart('main.png')",
                    "packages": ["pandas"],
                    "summary": "done",
                }

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                captured["args"] = args
                return {
                    "ok": True,
                    "run_id": "chr_opencode",
                    "image_url": "/charts/chr_opencode/main.png",
                    "meta_url": "/chart-runs/chr_opencode/meta",
                    "artifacts": [{"name": "main.png", "url": "/charts/chr_opencode/main.png", "size": 111}],
                    "installed_packages": args.get("packages") or [],
                    "python_executable": "python3",
                }

            app_mod.resolve_opencode_status = fake_status  # type: ignore[attr-defined]
            app_mod.run_opencode_codegen = fake_opencode  # type: ignore[attr-defined]
            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]

            res = app_mod.tool_dispatch(
                "chart.agent.run",
                {
                    "task": "画一个趋势图",
                    "engine": "opencode",
                    "input_data": {"x": [1, 2, 3], "y": [2, 4, 3]},
                    "packages": ["numpy"],
                },
                role="teacher",
            )
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("engine_used"), "opencode")
            self.assertEqual(res.get("engine_requested"), "opencode")
            exec_args = captured.get("args") or {}
            self.assertIn("numpy", exec_args.get("packages") or [])
            self.assertIn("pandas", exec_args.get("packages") or [])

    def test_chart_agent_run_forced_opencode_unavailable(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))

            def fake_status(app_root, overrides=None):  # type: ignore[no-untyped-def]
                return {"enabled": True, "available": False, "reason": "binary_not_found", "config": {}}

            app_mod.resolve_opencode_status = fake_status  # type: ignore[attr-defined]
            res = app_mod.tool_dispatch(
                "chart.agent.run",
                {"task": "画图", "engine": "opencode"},
                role="teacher",
            )
            self.assertFalse(res.get("ok"))
            self.assertEqual(res.get("error"), "opencode_unavailable")

    def test_chart_agent_run_auto_fallback_to_llm(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))

            def fake_status(app_root, overrides=None):  # type: ignore[no-untyped-def]
                return {
                    "enabled": True,
                    "available": True,
                    "reason": "ok",
                    "binary": "/usr/local/bin/opencode",
                    "config": {"max_retries": 2},
                }

            def fake_opencode(**kwargs):  # type: ignore[no-untyped-def]
                return {"ok": False, "error": "no_code", "python_code": "", "packages": [], "summary": ""}

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):  # type: ignore[no-untyped-def]
                payload = {
                    "python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2],[2,3])\nsave_chart()",
                    "packages": [],
                    "summary": "fallback",
                }
                return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                return {
                    "ok": True,
                    "run_id": "chr_auto",
                    "image_url": "/charts/chr_auto/main.png",
                    "meta_url": "/chart-runs/chr_auto/meta",
                    "artifacts": [{"name": "main.png", "url": "/charts/chr_auto/main.png", "size": 99}],
                    "installed_packages": [],
                    "python_executable": "python3",
                }

            app_mod.resolve_opencode_status = fake_status  # type: ignore[attr-defined]
            app_mod.run_opencode_codegen = fake_opencode  # type: ignore[attr-defined]
            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]
            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]

            res = app_mod.tool_dispatch(
                "chart.agent.run",
                {"task": "画图", "engine": "auto"},
                role="teacher",
            )
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("engine_used"), "llm")

    def test_chart_agent_run_default_engine_prefers_opencode(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))

            def fake_status(app_root, overrides=None):  # type: ignore[no-untyped-def]
                return {
                    "enabled": True,
                    "available": True,
                    "reason": "ok",
                    "binary": "/usr/local/bin/opencode",
                    "config": {"max_retries": 2},
                }

            def fake_opencode(**kwargs):  # type: ignore[no-untyped-def]
                return {
                    "ok": True,
                    "python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2,3],[2,3,4])\nsave_chart('main.png')",
                    "packages": ["pandas"],
                    "summary": "ok",
                }

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                return {
                    "ok": True,
                    "run_id": "chr_default",
                    "image_url": "/charts/chr_default/main.png",
                    "meta_url": "/chart-runs/chr_default/meta",
                    "artifacts": [{"name": "main.png", "url": "/charts/chr_default/main.png", "size": 88}],
                    "installed_packages": args.get("packages") or [],
                    "python_executable": "python3",
                }

            app_mod.resolve_opencode_status = fake_status  # type: ignore[attr-defined]
            app_mod.run_opencode_codegen = fake_opencode  # type: ignore[attr-defined]
            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]

            res = app_mod.tool_dispatch(
                "chart.agent.run",
                {"task": "画图", "input_data": {"a": 1}},
                role="teacher",
            )
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("engine_requested"), "opencode")
            self.assertEqual(res.get("engine_used"), "opencode")


if __name__ == "__main__":
    unittest.main()
