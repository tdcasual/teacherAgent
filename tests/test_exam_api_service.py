import unittest

from services.api.exam_api_service import ExamApiDeps, get_exam_detail_api


class ExamApiServiceTest(unittest.TestCase):
    def test_get_exam_detail_maps_not_found(self):
        deps = ExamApiDeps(exam_get=lambda _eid: {"error": "not_found"})
        payload = get_exam_detail_api("E1", deps=deps)
        self.assertEqual(payload["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
