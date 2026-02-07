import unittest

from services.api.teacher_routing_api_service import TeacherRoutingApiDeps, get_routing_api


class TeacherRoutingApiServiceTest(unittest.TestCase):
    def test_get_routing_api_delegates(self):
        deps = TeacherRoutingApiDeps(teacher_llm_routing_get=lambda _args: {"ok": True})
        self.assertTrue(get_routing_api({}, deps=deps)["ok"])


if __name__ == "__main__":
    unittest.main()
