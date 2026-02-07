import unittest

from services.api.assignment_api_service import AssignmentApiDeps, get_assignment_detail_api


class AssignmentApiServiceTest(unittest.TestCase):
    def test_get_assignment_detail_api_passthrough(self):
        deps = AssignmentApiDeps(
            build_assignment_detail=lambda _folder, include_text=True: {"assignment_id": "A1"}
        )
        self.assertEqual(get_assignment_detail_api("A1", deps=deps)["assignment_id"], "A1")


if __name__ == "__main__":
    unittest.main()
