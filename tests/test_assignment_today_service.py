import unittest

from services.api.assignment_today_service import AssignmentTodayDeps, AssignmentTodayError, assignment_today


class AssignmentTodayServiceTest(unittest.TestCase):
    def test_returns_empty_assignments_without_top_level_object(self):
        deps = AssignmentTodayDeps(
            parse_date_str=lambda value: str(value or "2026-02-08"),
            list_student_today=lambda *_args, **_kwargs: [],
        )
        result = assignment_today(
            student_id="S1",
            date="2026-02-08",
            auto_generate=False,
            generate=True,
            per_kp=5,
            deps=deps,
        )
        self.assertEqual(result, {"date": "2026-02-08", "assignments": []})
        self.assertNotIn("assignment", result)

    def test_auto_generate_true_raises_disabled(self):
        deps = AssignmentTodayDeps(
            parse_date_str=lambda value: str(value or "2026-02-08"),
            list_student_today=lambda *_args, **_kwargs: [{"assignment_id": "nope"}],
        )
        with self.assertRaises(AssignmentTodayError) as ctx:
            assignment_today(
                student_id="S1",
                date="2026-02-08",
                auto_generate=True,
                generate=True,
                per_kp=5,
                deps=deps,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "auto_generate_disabled")


if __name__ == "__main__":
    unittest.main()
