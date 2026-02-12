from __future__ import annotations

import unittest

from services.api.chart_agent_run_service import ChartAgentRunDeps, chart_agent_run


class ChartAgentRunServiceTest(unittest.TestCase):
    def _deps(self):
        return ChartAgentRunDeps(
            safe_int_arg=lambda value, default, minimum, maximum: max(
                minimum, min(maximum, int(default if value is None else value))
            ),
            chart_bool=lambda value, default: default if value is None else bool(value),
            chart_engine=lambda value: (str(value or "").strip().lower() or "llm"),
            chart_packages=lambda value: [str(v).strip() for v in (value or []) if str(v).strip()]
            if isinstance(value, list)
            else [],
            chart_opencode_overrides=lambda args: {},
            resolve_opencode_status=lambda app_root, overrides=None: {
                "enabled": True,
                "available": False,
                "reason": "binary_not_found",
                "config": {},
            },
            app_root="/tmp/app",
            uploads_dir="/tmp/uploads",
            generate_candidate=lambda task, input_data, last_error, previous_code, attempt, max_retries: {
                "python_code": "print('ok')",
                "packages": ["pandas"],
                "summary": "ok",
            },
            generate_candidate_opencode=lambda task, input_data, last_error, previous_code, attempt, max_retries, opencode_overrides: {
                "python_code": "",
                "packages": [],
                "summary": "",
            },
            execute_chart_exec=lambda args, app_root, uploads_dir: {
                "ok": True,
                "run_id": "run_1",
                "image_url": "/charts/run_1/main.png",
                "meta_url": "/chart-runs/run_1/meta",
                "artifacts": [],
                "installed_packages": args.get("packages") or [],
                "python_executable": "python3",
            },
            default_code=lambda: "print('default')",
        )

    def test_chart_agent_run_requires_task(self):
        result = chart_agent_run({}, deps=self._deps())
        self.assertEqual(result, {"error": "task_required"})

    def test_chart_agent_run_success_merges_package_lists(self):
        deps = self._deps()
        result = chart_agent_run(
            {"task": "画图", "packages": ["numpy"]},
            deps=deps,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("attempt_used"), 1)
        attempts = result.get("attempts") or []
        self.assertEqual(attempts[0].get("packages"), ["numpy", "pandas"])

    def test_forced_opencode_unavailable_returns_error(self):
        deps = self._deps()
        result = chart_agent_run(
            {"task": "画图", "engine": "opencode"},
            deps=deps,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "opencode_forbidden")
        self.assertEqual(result.get("status_code"), 400)

    def test_chart_agent_run_rejects_success_when_cjk_glyphs_missing(self):
        deps = self._deps()
        deps = ChartAgentRunDeps(
            **{
                **deps.__dict__,
                "generate_candidate": lambda task, input_data, last_error, previous_code, attempt, max_retries: {
                    "python_code": "import matplotlib.pyplot as plt\nplt.title('线性关系散点图示例')\nsave_chart()",
                    "packages": [],
                    "summary": "try_cjk",
                },
                "execute_chart_exec": lambda args, app_root, uploads_dir: {
                    "ok": True,
                    "run_id": "run_cjk",
                    "image_url": "/charts/run_cjk/main.png",
                    "meta_url": "/chart-runs/run_cjk/meta",
                    "artifacts": [],
                    "installed_packages": [],
                    "python_executable": "python3",
                    "stderr": "UserWarning: Glyph 32447 (\\N{CJK UNIFIED IDEOGRAPH-7EBF}) missing from font(s) DejaVu Sans.",
                },
            }
        )
        result = chart_agent_run(
            {"task": "画一个中文标题图", "max_retries": 1},
            deps=deps,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "chart_agent_unresolved_warnings")
        self.assertIn("missing_cjk_glyphs", str(result.get("last_error") or ""))

    def test_chart_agent_run_retries_when_actionable_warning_detected(self):
        deps = self._deps()
        state = {"attempt": 0}

        def fake_codegen(task, input_data, last_error, previous_code, attempt, max_retries):  # type: ignore[no-untyped-def]
            state["attempt"] = attempt
            return {
                "python_code": "import matplotlib.pyplot as plt\nplt.plot([1,2],[2,3])\nsave_chart()",
                "packages": [],
                "summary": f"attempt_{attempt}",
            }

        def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
            if state["attempt"] == 1:
                return {
                    "ok": True,
                    "run_id": "run_warn",
                    "image_url": "/charts/run_warn/main.png",
                    "meta_url": "/chart-runs/run_warn/meta",
                    "artifacts": [],
                    "installed_packages": [],
                    "python_executable": "python3",
                    "stderr": "<chart.exec>:11: UserWarning: Tight layout not applied.",
                }
            return {
                "ok": True,
                "run_id": "run_clean",
                "image_url": "/charts/run_clean/main.png",
                "meta_url": "/chart-runs/run_clean/meta",
                "artifacts": [],
                "installed_packages": [],
                "python_executable": "python3",
                "stderr": "",
            }

        deps = ChartAgentRunDeps(
            **{
                **deps.__dict__,
                "generate_candidate": fake_codegen,
                "execute_chart_exec": fake_execute,
            }
        )
        result = chart_agent_run(
            {"task": "画图并消除warning", "max_retries": 2},
            deps=deps,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("attempt_used"), 2)

    def test_chart_agent_run_ignores_benign_runtime_warning_noise(self):
        deps = self._deps()
        deps = ChartAgentRunDeps(
            **{
                **deps.__dict__,
                "execute_chart_exec": lambda args, app_root, uploads_dir: {
                    "ok": True,
                    "run_id": "run_noise",
                    "image_url": "/charts/run_noise/main.png",
                    "meta_url": "/chart-runs/run_noise/meta",
                    "artifacts": [],
                    "installed_packages": [],
                    "python_executable": "python3",
                    "stderr": (
                        "mkdir -p failed for path /home/appuser/.config/matplotlib\n"
                        "Matplotlib created a temporary cache directory at /tmp/mpl\n"
                        "Could not save font_manager cache sandbox: write denied outside output dir\n"
                    ),
                },
            }
        )
        result = chart_agent_run(
            {"task": "简单画图", "max_retries": 1},
            deps=deps,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("attempt_used"), 1)


if __name__ == "__main__":
    unittest.main()
