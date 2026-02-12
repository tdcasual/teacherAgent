import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.api.assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    _resolve_submission_base,
    best_submission_attempt,
    compute_submission_attempt,
    counted_grade_item,
    list_submission_attempts,
)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class AssignmentSubmissionAttemptServiceTest(unittest.TestCase):
    def test_resolve_submission_base_rejects_empty_ids(self):
        root = Path("/tmp/submissions")
        self.assertIsNone(_resolve_submission_base(root, "", "S1"))
        self.assertIsNone(_resolve_submission_base(root, "A1", ""))

    def test_counted_grade_item_handles_bad_get_and_bad_confidence(self):
        deps = AssignmentSubmissionAttemptDeps(
            student_submissions_dir=Path("/tmp/submissions"),
            grade_count_conf_threshold=0.8,
        )

        class BadStatusItem(dict):
            def get(self, key, default=None):  # type: ignore[override]
                if key == "status":
                    raise RuntimeError("status error")
                if key == "confidence":
                    raise RuntimeError("confidence error")
                return default

        self.assertFalse(counted_grade_item(BadStatusItem(), deps=deps))

    def test_compute_submission_attempt_counts_only_confident_graded_items(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempt_dir = root / "attempts" / "submission_20260207_101500"
            _write_json(
                attempt_dir / "grading_report.json",
                {
                    "graded_total": 1,
                    "correct": 1,
                    "ungraded": 1,
                    "items": [
                        {"status": "matched", "confidence": 0.95, "score": 4},
                        {"status": "ungraded", "confidence": 1.0, "score": 4},
                        {"status": "matched", "confidence": 0.6, "score": 4},
                    ],
                },
            )

            result = compute_submission_attempt(attempt_dir, deps=deps)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["attempt_id"], "submission_20260207_101500")
            self.assertEqual(result["score_earned"], 4.0)
            self.assertTrue(result["valid_submission"])

    def test_compute_submission_attempt_returns_none_when_report_missing(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempt_dir = root / "attempts" / "submission_20260207_101500"
            self.assertIsNone(compute_submission_attempt(attempt_dir, deps=deps))

    def test_compute_submission_attempt_handles_invalid_numeric_fields(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempt_dir = root / "attempts" / "submission_misc"
            _write_json(
                attempt_dir / "grading_report.json",
                {
                    "graded_total": "bad",
                    "correct": "bad",
                    "ungraded": "bad",
                    "items": [
                        {"status": "matched", "confidence": 0.95, "score": "bad"},
                        {"status": "matched", "confidence": 0.9, "score": 2},
                        "unexpected",
                    ],
                },
            )
            result = compute_submission_attempt(attempt_dir, deps=deps)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["graded_total"], 2)
            self.assertEqual(result["correct"], 0)
            self.assertEqual(result["ungraded"], 0)
            self.assertEqual(result["score_earned"], 2.0)
            self.assertTrue(bool(result["submitted_at"]))

    def test_compute_submission_attempt_returns_none_for_corrupt_or_non_dict_report(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempt_dir = root / "attempts" / "submission_20260207_101500"
            report_path = attempt_dir / "grading_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)

            report_path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(compute_submission_attempt(attempt_dir, deps=deps))

            report_path.write_text(json.dumps(["not-a-dict"]), encoding="utf-8")
            self.assertIsNone(compute_submission_attempt(attempt_dir, deps=deps))

    def test_compute_submission_attempt_normalizes_non_list_items(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempt_dir = root / "attempts" / "submission_20260207_101500"
            _write_json(
                attempt_dir / "grading_report.json",
                {
                    "graded_total": 1,
                    "correct": 1,
                    "ungraded": 0,
                    "items": {"unexpected": "dict"},
                },
            )
            result = compute_submission_attempt(attempt_dir, deps=deps)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["score_earned"], 0.0)

    def test_compute_submission_attempt_uses_empty_submitted_at_when_all_time_parsers_fail(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempt_dir = root / "attempts" / "submission_20260207_101500"
            _write_json(
                attempt_dir / "grading_report.json",
                {
                    "graded_total": 1,
                    "correct": 1,
                    "ungraded": 0,
                    "items": [{"status": "matched", "confidence": 1.0, "score": 1}],
                },
            )

            with patch("services.api.assignment_submission_attempt_service.datetime") as dt_mock:
                dt_mock.strptime.side_effect = RuntimeError("parse failure")
                dt_mock.fromtimestamp.side_effect = RuntimeError("fallback failure")
                result = compute_submission_attempt(attempt_dir, deps=deps)

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["submitted_at"], "")

    def test_list_submission_attempts_scans_assignment_student_folder(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            _write_json(
                deps.student_submissions_dir / "A1" / "S1" / "submission_20260207_101500" / "grading_report.json",
                {"graded_total": 1, "correct": 1, "ungraded": 0, "items": [{"status": "matched", "confidence": 1, "score": 3}]},
            )
            _write_json(
                deps.student_submissions_dir / "A1" / "S1" / "submission_20260207_111500" / "grading_report.json",
                {"graded_total": 0, "correct": 0, "ungraded": 1, "items": [{"status": "ungraded", "confidence": 1, "score": 0}]},
            )

            attempts = list_submission_attempts("A1", "S1", deps=deps)
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["attempt_id"], "submission_20260207_101500")
            self.assertEqual(attempts[1]["attempt_id"], "submission_20260207_111500")

    def test_list_submission_attempts_ignores_non_directories_and_missing_base(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            base = deps.student_submissions_dir / "A1" / "S1"
            base.mkdir(parents=True, exist_ok=True)
            (base / "submission_20260207_101500").write_text("not-dir", encoding="utf-8")
            attempts = list_submission_attempts("A1", "S1", deps=deps)
            self.assertEqual(attempts, [])
            self.assertEqual(list_submission_attempts("A1", "S2", deps=deps), [])

    def test_best_submission_attempt_prefers_score_then_correct_then_graded_total(self):
        attempts = [
            {"attempt_id": "a1", "valid_submission": True, "score_earned": 6, "correct": 6, "graded_total": 10, "submitted_at": "2026-02-07T10:00:00"},
            {"attempt_id": "a2", "valid_submission": True, "score_earned": 8, "correct": 8, "graded_total": 10, "submitted_at": "2026-02-07T11:00:00"},
            {"attempt_id": "a3", "valid_submission": True, "score_earned": 8, "correct": 7, "graded_total": 10, "submitted_at": "2026-02-07T12:00:00"},
            {"attempt_id": "a4", "valid_submission": False, "score_earned": 9, "correct": 9, "graded_total": 10, "submitted_at": "2026-02-07T13:00:00"},
        ]
        best = best_submission_attempt(attempts)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best["attempt_id"], "a2")

    def test_best_submission_attempt_handles_invalid_timestamp(self):
        attempts = [
            {"attempt_id": "bad-ts", "valid_submission": True, "score_earned": 8, "correct": 8, "graded_total": 10, "submitted_at": "not-iso"},
            {"attempt_id": "good-ts", "valid_submission": True, "score_earned": 8, "correct": 8, "graded_total": 10, "submitted_at": "2026-02-07T11:00:00"},
        ]
        best = best_submission_attempt(attempts)
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best["attempt_id"], "good-ts")

    def test_best_submission_attempt_returns_none_without_valid_attempt(self):
        attempts = [
            {"attempt_id": "a1", "valid_submission": False, "score_earned": 10, "correct": 10, "graded_total": 10},
            {"attempt_id": "a2", "score_earned": 9, "correct": 9, "graded_total": 10},
        ]
        self.assertIsNone(best_submission_attempt(attempts))

    def test_list_submission_attempts_rejects_traversal_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = AssignmentSubmissionAttemptDeps(
                student_submissions_dir=root / "student_submissions",
                grade_count_conf_threshold=0.8,
            )
            attempts = list_submission_attempts("../escape", "S1", deps=deps)
            self.assertEqual(attempts, [])


if __name__ == "__main__":
    unittest.main()
