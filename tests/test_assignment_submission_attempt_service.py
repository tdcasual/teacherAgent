import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_submission_attempt_service import (
    AssignmentSubmissionAttemptDeps,
    best_submission_attempt,
    compute_submission_attempt,
    list_submission_attempts,
)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class AssignmentSubmissionAttemptServiceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
