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


if __name__ == "__main__":
    unittest.main()
