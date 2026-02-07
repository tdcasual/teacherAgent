import unittest

from services.api.chat_session_utils import paginate_session_items, resolve_student_session_id


class ChatSessionUtilsTest(unittest.TestCase):
    def test_resolve_student_session_id_prefers_assignment_id(self):
        session_id = resolve_student_session_id(
            student_id="S001",
            assignment_id="A-001",
            assignment_date="2026-02-01",
            parse_date_str=lambda value: value or "1970-01-01",
        )
        self.assertEqual(session_id, "A-001")

    def test_resolve_student_session_id_falls_back_to_date(self):
        session_id = resolve_student_session_id(
            student_id="S001",
            assignment_id=None,
            assignment_date="2026-02-01",
            parse_date_str=lambda value: value or "1970-01-01",
        )
        self.assertEqual(session_id, "general_2026-02-01")

    def test_paginate_session_items_returns_page_and_next_cursor(self):
        items = [{"id": i} for i in range(10)]
        page, next_cursor, total = paginate_session_items(items, cursor=2, limit=3)
        self.assertEqual(total, 10)
        self.assertEqual(page, [{"id": 2}, {"id": 3}, {"id": 4}])
        self.assertEqual(next_cursor, 5)

    def test_paginate_session_items_clamps_and_handles_out_of_range(self):
        items = [{"id": i} for i in range(2)]
        page, next_cursor, total = paginate_session_items(items, cursor=99, limit=10)
        self.assertEqual(total, 2)
        self.assertEqual(page, [])
        self.assertIsNone(next_cursor)


if __name__ == "__main__":
    unittest.main()
