import unittest

from services.api.student_profile_api_service import StudentProfileApiDeps, get_profile_api


class StudentProfileApiServiceTest(unittest.TestCase):
    def test_get_profile_api_delegates(self):
        deps = StudentProfileApiDeps(student_profile_get=lambda sid: {"student_id": sid})
        self.assertEqual(get_profile_api("S1", deps=deps)["student_id"], "S1")


if __name__ == "__main__":
    unittest.main()
