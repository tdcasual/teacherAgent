import unittest

from services.api.chart_api_service import ChartApiDeps, chart_exec_api


class ChartApiServiceTest(unittest.TestCase):
    def test_chart_exec_api_delegates(self):
        deps = ChartApiDeps(chart_exec=lambda args: {"ok": True, "args": args})
        self.assertTrue(chart_exec_api({"run": 1}, deps=deps)["ok"])


if __name__ == "__main__":
    unittest.main()
