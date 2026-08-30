from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_student_list_service import (
    StudentAssignmentListDeps,
    assigned_date_of,
    list_assignments_for_student,
    list_student_assignment_history,
    local_overdue,
)
from services.api.assignment_today_service import (
    AssignmentTodayDeps,
    AssignmentTodayError,
    assignment_today,
)


def _write_meta(root: Path, assignment_id: str, meta: dict) -> Path:
    folder = root / "data" / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"assignment_id": assignment_id, **meta}
    (folder / "meta.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return folder


def _deps(
    root: Path,
    *,
    enrolled: set[tuple[str, str, str]] | None = None,
    attempts: dict[tuple[str, str], list] | None = None,
    lookback_days: int = 14,
) -> StudentAssignmentListDeps:
    enrolled_set = enrolled or set()
    attempt_map = attempts or {}
    return StudentAssignmentListDeps(
        data_dir=root / "data",
        load_assignment_meta=lambda folder: json.loads((folder / "meta.json").read_text(encoding="utf-8")),
        student_enrolled=lambda sid, tid, sub: (sid, tid, sub) in enrolled_set,
        list_submission_attempts=lambda aid, sid: list(attempt_map.get((aid, sid), [])),
        lookback_days=lookback_days,
    )


_PUBLISHED = {
    "visibility_status": "published",
    "teacher_id": "t_zhang",
    "subject_id": "physics",
    "title": "力学练习",
    "expected_students": ["S1"],
    "date": "2026-08-20",
    "generated_at": "2026-08-20T09:00:00",
}


class AssignedDateTests(unittest.TestCase):
    def test_uses_meta_date_when_set(self):
        self.assertEqual(assigned_date_of({"date": "2026-08-20", "generated_at": "2026-08-01T00:00:00"}), date(2026, 8, 20))

    def test_falls_back_to_generated_at_date(self):
        self.assertEqual(assigned_date_of({"date": "", "generated_at": "2026-08-01T12:00:00"}), date(2026, 8, 1))

    def test_empty_date_is_not_coerced_to_today(self):
        self.assertIsNone(assigned_date_of({"date": "", "generated_at": ""}))
        self.assertIsNone(assigned_date_of({}))


class LocalOverdueTests(unittest.TestCase):
    def test_overdue_is_due_date_before_today_and_not_submitted(self):
        today = date(2026, 8, 28)
        self.assertTrue(local_overdue(today, "2026-08-27T23:59:59", submitted=False))
        self.assertFalse(local_overdue(today, "2026-08-28T23:59:59", submitted=False))
        self.assertFalse(local_overdue(today, "2026-08-27T23:59:59", submitted=True))
        self.assertFalse(local_overdue(today, "", submitted=False))


class ListAssignmentsForStudentTests(unittest.TestCase):
    def test_visibility_table_and_sort(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_FUTURE", {**_PUBLISHED, "date": "2026-08-30"})
            _write_meta(root, "HW_ARCHIVED", {**_PUBLISHED, "visibility_status": "archived"})
            _write_meta(root, "HW_DRAFT", {**_PUBLISHED, "visibility_status": "draft"})
            _write_meta(root, "HW_NO_OWNER", {**_PUBLISHED, "teacher_id": ""})
            _write_meta(root, "HW_LOOKBACK", {**_PUBLISHED, "date": "2026-08-01", "due_at": ""})
            _write_meta(
                root,
                "HW_OVERDUE",
                {**_PUBLISHED, "subject_id": "math", "teacher_id": "t_li", "due_at": "2026-08-20T18:00:00"},
            )
            _write_meta(
                root,
                "HW_OVERDUE_DONE",
                {**_PUBLISHED, "due_at": "2026-08-20T18:00:00", "title": "已交逾期"},
            )
            _write_meta(
                root,
                "HW_TODAY",
                {**_PUBLISHED, "date": "2026-08-28", "due_at": "2026-08-29T23:59:59", "title": "今日物理"},
            )
            _write_meta(
                root,
                "HW_TODAY_DONE",
                {**_PUBLISHED, "date": "2026-08-28", "due_at": "2026-08-29T23:59:59", "title": "已交今日"},
            )
            _write_meta(
                root,
                "HW_EMPTY_DUE",
                {**_PUBLISHED, "date": "2026-08-27", "due_at": "", "subject_id": "physics", "title": "无截止"},
            )

            enrolled = {
                ("S1", "t_zhang", "physics"),
                ("S1", "t_li", "math"),
            }
            attempts = {
                ("HW_OVERDUE_DONE", "S1"): [{"valid_submission": True, "score_earned": 9, "submitted_at": "2026-08-21T10:00:00"}],
                ("HW_TODAY_DONE", "S1"): [{"valid_submission": True, "score_earned": 8, "submitted_at": "2026-08-28T10:00:00"}],
            }
            items = list_assignments_for_student(
                student_id="S1",
                date_str="2026-08-28",
                deps=_deps(root, enrolled=enrolled, attempts=attempts),
            )
            ids = [item["assignment_id"] for item in items]
            self.assertEqual(ids, ["HW_OVERDUE", "HW_TODAY", "HW_EMPTY_DUE"])
            self.assertTrue(items[0]["progress"]["overdue"])
            self.assertFalse(items[0]["progress"]["submitted"])
            self.assertEqual(items[2]["due_at"], "")
            self.assertNotIn("assignment", {"assignments": items})

    def test_unenrolled_student_is_hidden_even_if_on_snapshot(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", _PUBLISHED)
            items = list_assignments_for_student(
                student_id="S1",
                date_str="2026-08-28",
                deps=_deps(root, enrolled=set()),
            )
            self.assertEqual(items, [])

    def test_requires_discussion_does_not_keep_submitted_item_overdue(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(
                root,
                "HW_1",
                {
                    **_PUBLISHED,
                    "due_at": "2026-08-20T18:00:00",
                    "completion_policy": {"requires_discussion": True, "requires_submission": True},
                },
            )
            items = list_assignments_for_student(
                student_id="S1",
                date_str="2026-08-28",
                deps=_deps(
                    root,
                    enrolled={("S1", "t_zhang", "physics")},
                    attempts={
                        ("HW_1", "S1"): [{"valid_submission": True, "score_earned": 10, "submitted_at": "2026-08-21T09:00:00"}]
                    },
                ),
            )
            self.assertEqual(items, [])

    def test_empty_assigned_date_is_hidden_unless_overdue_unsubmitted(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_NODATE", {**_PUBLISHED, "date": "", "generated_at": "", "due_at": ""})
            _write_meta(
                root,
                "HW_NODATE_OVERDUE",
                {**_PUBLISHED, "date": "", "generated_at": "", "due_at": "2026-08-01T00:00:00"},
            )
            items = list_assignments_for_student(
                student_id="S1",
                date_str="2026-08-28",
                deps=_deps(root, enrolled={("S1", "t_zhang", "physics")}),
            )
            self.assertEqual([item["assignment_id"] for item in items], ["HW_NODATE_OVERDUE"])


class StudentAssignmentHistoryTests(unittest.TestCase):
    def test_history_includes_published_live_and_archived_frozen(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_LIVE", {**_PUBLISHED, "date": "2026-08-01"})
            _write_meta(
                root,
                "HW_ARCHIVED",
                {
                    **_PUBLISHED,
                    "visibility_status": "archived",
                    "archived_at": "2026-08-25T12:00:00",
                    "title": "归档物理",
                },
            )
            _write_meta(root, "HW_DRAFT", {**_PUBLISHED, "visibility_status": "draft"})
            _write_meta(
                root,
                "HW_UNENROLLED",
                {**_PUBLISHED, "assignment_id": "HW_UNENROLLED", "title": "已退班"},
            )
            result = list_student_assignment_history(
                student_id="S1",
                limit=50,
                cursor=0,
                deps=_deps(root, enrolled={("S1", "t_zhang", "physics")}),
            )
            ids = [item["assignment_id"] for item in result["assignments"]]
            self.assertIn("HW_LIVE", ids)
            self.assertIn("HW_ARCHIVED", ids)
            self.assertNotIn("HW_DRAFT", ids)

    def test_history_published_hides_after_unenroll_archived_keeps_frozen_snapshot(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_LIVE", _PUBLISHED)
            _write_meta(
                root,
                "HW_ARCHIVED",
                {**_PUBLISHED, "visibility_status": "archived", "archived_at": "2026-08-25T12:00:00"},
            )
            result = list_student_assignment_history(
                student_id="S1",
                limit=50,
                cursor=0,
                deps=_deps(root, enrolled=set()),
            )
            ids = [item["assignment_id"] for item in result["assignments"]]
            self.assertEqual(ids, ["HW_ARCHIVED"])
            self.assertEqual(result["assignments"][0]["visibility_status"], "archived")


class AssignmentTodayServiceTests(unittest.TestCase):
    def test_returns_assignments_list_without_top_level_assignment(self):
        deps = AssignmentTodayDeps(
            parse_date_str=lambda value: str(value or "2026-08-28"),
            list_student_today=lambda student_id, date_str: [
                {
                    "assignment_id": "HW_1",
                    "teacher_id": "t_zhang",
                    "subject_id": "physics",
                    "title": "力学",
                    "due_at": "2026-08-29T23:59:59",
                    "progress": {
                        "submitted": False,
                        "overdue": False,
                        "official_score": None,
                        "process_archive_status": "none",
                    },
                }
            ],
        )
        result = assignment_today(
            student_id="S1",
            date=None,
            auto_generate=False,
            generate=True,
            per_kp=5,
            deps=deps,
        )
        self.assertEqual(result["date"], "2026-08-28")
        self.assertEqual(len(result["assignments"]), 1)
        self.assertNotIn("assignment", result)

    def test_auto_generate_true_is_disabled(self):
        deps = AssignmentTodayDeps(
            parse_date_str=lambda value: str(value or "2026-08-28"),
            list_student_today=lambda *_args, **_kwargs: [{"assignment_id": "should_not_run"}],
        )
        with self.assertRaises(AssignmentTodayError) as ctx:
            assignment_today(
                student_id="S1",
                date="2026-08-28",
                auto_generate=True,
                generate=True,
                per_kp=5,
                deps=deps,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "auto_generate_disabled")


if __name__ == "__main__":
    unittest.main()
