import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class AssignmentProgressTest(unittest.TestCase):
    def test_assignment_routes_use_assignment_api_deps(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            with TestClient(app_mod.app) as client:
                sentinel = object()
                captured = {}

                def _fake_impl(assignment_id: str, *, deps):
                    captured["assignment_id"] = assignment_id
                    captured["deps"] = deps
                    return {"assignment_id": assignment_id}

                app_mod._get_assignment_detail_api_impl = _fake_impl
                app_mod._assignment_api_deps = lambda: sentinel

                res = client.get("/assignment/A1")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(captured.get("assignment_id"), "A1")
                self.assertIs(captured.get("deps"), sentinel)

    def test_progress_endpoint_returns_404_for_missing_assignment(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": "DOES_NOT_EXIST"})
                self.assertEqual(res.status_code, 404)

    def test_include_students_false_returns_empty_students_but_keeps_counts(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            assignment_id = "HW_INCLUDE_FLAG_2026-02-05"
            write_json(
                tmp / "data" / "assignments" / assignment_id / "meta.json",
                {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "student", "student_ids": ["S001"]},
            )
            with TestClient(app_mod.app) as client:
                res = client.get(
                    "/teacher/assignment/progress",
                    params={"assignment_id": assignment_id, "include_students": "false"},
                )
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["ok"])
                self.assertEqual(data["counts"]["expected"], 1)
                self.assertEqual(data["students"], [])

    def test_student_scope_expected_students_dedup_and_sorted(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            write_json(tmp / "data" / "student_profiles" / "S002.json", {"student_id": "S002"})
            assignment_id = "HW_STUDENT_DEDUP_2026-02-05"
            write_json(
                tmp / "data" / "assignments" / assignment_id / "meta.json",
                {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "student", "student_ids": ["S002", "S001", "S001"]},
            )
            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["expected_count"], 2)
                ids = [s.get("student_id") for s in data.get("students") or []]
                self.assertEqual(sorted(ids), ["S001", "S002"])
    def test_public_expected_students_and_completion(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            # seed students
            write_json(
                tmp / "data" / "student_profiles" / "S001.json",
                {"student_id": "S001", "student_name": "张三", "class_name": "高二2403班"},
            )
            write_json(
                tmp / "data" / "student_profiles" / "S002.json",
                {"student_id": "S002", "student_name": "李四", "class_name": "高二2403班"},
            )

            assignment_id = "HW_2026-02-05"
            write_json(
                tmp / "data" / "assignments" / assignment_id / "meta.json",
                {
                    "assignment_id": assignment_id,
                    "date": "2026-02-05",
                    "scope": "public",
                    "class_name": "",
                    "student_ids": [],
                    "source": "teacher",
                    "generated_at": "2026-02-05T10:00:00",
                },
            )

            # S001: discussion pass marker + graded submission
            sess_path = app_mod.student_session_file("S001", assignment_id)
            sess_path.parent.mkdir(parents=True, exist_ok=True)
            sess_path.write_text(
                json.dumps(
                    {
                        "ts": "2026-02-05T10:10:00",
                        "role": "assistant",
                        "content": f"{app_mod.DISCUSSION_COMPLETE_MARKER}\n1) ...",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            report = {
                "student_id": "S001",
                "assignment_id": assignment_id,
                "graded_total": 1,
                "ungraded": 0,
                "correct": 1,
                "items": [{"question_id": "Q1", "status": "matched", "confidence": 1.0, "score": 1.0}],
            }
            write_json(
                tmp
                / "data"
                / "student_submissions"
                / assignment_id
                / "S001"
                / "submission_20260205_101500"
                / "grading_report.json",
                report,
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["ok"])
                self.assertEqual(data["expected_count"], 2)
                self.assertEqual(data["counts"]["completed"], 1)

                s1 = next(s for s in data["students"] if s.get("student_id") == "S001")
                s2 = next(s for s in data["students"] if s.get("student_id") == "S002")
                self.assertTrue(s1["complete"])
                self.assertFalse(s2["complete"])

    def test_best_attempt_selection_prefers_score_then_correct_then_graded_total(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001", "student_name": "张三"})
            assignment_id = "HW2_2026-02-05"
            write_json(tmp / "data" / "assignments" / assignment_id / "meta.json", {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "student", "student_ids": ["S001"]})

            # Discussion marker so completion depends only on submission best attempt.
            sess_path = app_mod.student_session_file("S001", assignment_id)
            sess_path.parent.mkdir(parents=True, exist_ok=True)
            sess_path.write_text(
                json.dumps(
                    {"ts": "2026-02-05T10:10:00", "role": "assistant", "content": app_mod.DISCUSSION_COMPLETE_MARKER},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            # attempt A: 1/1
            write_json(
                tmp
                / "data"
                / "student_submissions"
                / assignment_id
                / "S001"
                / "submission_20260205_101000"
                / "grading_report.json",
                {
                    "student_id": "S001",
                    "assignment_id": assignment_id,
                    "graded_total": 1,
                    "ungraded": 0,
                    "correct": 1,
                    "items": [{"status": "matched", "confidence": 1.0, "score": 1.0}],
                },
            )

            # attempt B: 8/10
            items = []
            for i in range(1, 11):
                items.append(
                    {
                        "status": "matched" if i <= 8 else "missed",
                        "confidence": 1.0,
                        "score": 1.0 if i <= 8 else 0.0,
                    }
                )
            write_json(
                tmp
                / "data"
                / "student_submissions"
                / assignment_id
                / "S001"
                / "submission_20260205_102000"
                / "grading_report.json",
                {
                    "student_id": "S001",
                    "assignment_id": assignment_id,
                    "graded_total": 10,
                    "ungraded": 0,
                    "correct": 8,
                    "items": items,
                },
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                student = next(s for s in data["students"] if s.get("student_id") == "S001")
                best = student["submission"]["best"]
                self.assertEqual(best["attempt_id"], "submission_20260205_102000")
                self.assertEqual(best["score_earned"], 8.0)
                self.assertTrue(student["complete"])

    def test_graded_total_zero_does_not_count_as_submitted(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            assignment_id = "HW3_2026-02-05"
            write_json(tmp / "data" / "assignments" / assignment_id / "meta.json", {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "student", "student_ids": ["S001"]})

            # Discussion pass marker
            sess_path = app_mod.student_session_file("S001", assignment_id)
            sess_path.parent.mkdir(parents=True, exist_ok=True)
            sess_path.write_text(
                json.dumps(
                    {"ts": "2026-02-05T10:10:00", "role": "assistant", "content": app_mod.DISCUSSION_COMPLETE_MARKER},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            # graded_total = 0 (e.g., missing answer key or no detected answers)
            write_json(
                tmp
                / "data"
                / "student_submissions"
                / assignment_id
                / "S001"
                / "submission_20260205_101000"
                / "grading_report.json",
                {
                    "student_id": "S001",
                    "assignment_id": assignment_id,
                    "graded_total": 0,
                    "ungraded": 5,
                    "correct": 0,
                    "items": [{"status": "ungraded", "confidence": 0.0, "score": 0.0}],
                },
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["counts"]["submitted"], 0)
                student = next(s for s in data["students"] if s.get("student_id") == "S001")
                self.assertFalse(student["complete"])
                self.assertIsNone(student["submission"]["best"])

    def test_discussion_marker_can_be_found_via_session_index_fallback(self):
        """Regression: discussion completion should be detected even if session_id != assignment_id."""
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001", "student_name": "张三"})
            assignment_id = "HW4_2026-02-05"
            write_json(
                tmp / "data" / "assignments" / assignment_id / "meta.json",
                {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "student", "student_ids": ["S001"]},
            )

            # Session index points to a non-assignment session id
            index_path = app_mod.student_sessions_index_path("S001")
            write_json(
                index_path,
                [
                    {
                        "session_id": "general_2026-02-05",
                        "assignment_id": assignment_id,
                        "updated_at": "2026-02-05T10:00:00",
                        "message_count": 2,
                    }
                ],
            )

            # Session file contains the marker (assistant role)
            sess_path = app_mod.student_session_file("S001", "general_2026-02-05")
            sess_path.parent.mkdir(parents=True, exist_ok=True)
            sess_path.write_text(
                json.dumps(
                    {"ts": "2026-02-05T10:10:00", "role": "assistant", "content": app_mod.DISCUSSION_COMPLETE_MARKER},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            # Submission exists and graded -> complete should be true
            write_json(
                tmp
                / "data"
                / "student_submissions"
                / assignment_id
                / "S001"
                / "submission_20260205_101500"
                / "grading_report.json",
                {
                    "student_id": "S001",
                    "assignment_id": assignment_id,
                    "graded_total": 1,
                    "ungraded": 0,
                    "correct": 1,
                    "items": [{"status": "matched", "confidence": 1.0, "score": 1.0}],
                },
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                student = next(s for s in data["students"] if s.get("student_id") == "S001")
                self.assertTrue(student["discussion"]["pass"])
                self.assertTrue(student["complete"])

    def test_discussion_marker_in_user_message_is_ignored(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            assignment_id = "HW5_2026-02-05"
            write_json(tmp / "data" / "assignments" / assignment_id / "meta.json", {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "student", "student_ids": ["S001"]})

            # Marker appears in user role only -> should NOT count as discussion pass
            sess_path = app_mod.student_session_file("S001", assignment_id)
            sess_path.parent.mkdir(parents=True, exist_ok=True)
            sess_path.write_text(
                json.dumps(
                    {"ts": "2026-02-05T10:10:00", "role": "user", "content": app_mod.DISCUSSION_COMPLETE_MARKER},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                student = next(s for s in data["students"] if s.get("student_id") == "S001")
                self.assertFalse(student["discussion"]["pass"])
                self.assertFalse(student["complete"])

    def test_class_scope_expected_students_filtered_by_class(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001", "class_name": "高二2403班"})
            write_json(tmp / "data" / "student_profiles" / "S002.json", {"student_id": "S002", "class_name": "高二2404班"})

            assignment_id = "HW_CLASS_2026-02-05"
            write_json(
                tmp / "data" / "assignments" / assignment_id / "meta.json",
                {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "class", "class_name": "高二2403班"},
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["expected_count"], 1)
                self.assertEqual(data["students"][0]["student_id"], "S001")

    def test_due_at_normalization_and_overdue_flag(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            assignment_id = "HW_DUE_2026-02-05"
            # date-only due_at should normalize to end-of-day
            write_json(
                tmp / "data" / "assignments" / assignment_id / "meta.json",
                {
                    "assignment_id": assignment_id,
                    "date": "2026-02-05",
                    "scope": "student",
                    "student_ids": ["S001"],
                    "due_at": "2000-01-01",  # far past -> overdue
                },
            )

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                # normalized due_at
                self.assertEqual(data["due_at"], "2000-01-01T23:59:59")
                self.assertEqual(data["counts"]["overdue"], 1)
                student = next(s for s in data["students"] if s.get("student_id") == "S001")
                self.assertTrue(student["overdue"])

    def test_expected_students_snapshot_does_not_expand_after_new_students_added(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            assignment_id = "HW_SNAPSHOT_2026-02-05"
            write_json(tmp / "data" / "assignments" / assignment_id / "meta.json", {"assignment_id": assignment_id, "date": "2026-02-05", "scope": "public"})

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                first = res.json()
                self.assertEqual(first["expected_count"], 1)

                # add new student after snapshot
                write_json(tmp / "data" / "student_profiles" / "S002.json", {"student_id": "S002"})
                res = client.get("/teacher/assignment/progress", params={"assignment_id": assignment_id})
                self.assertEqual(res.status_code, 200)
                second = res.json()
                self.assertEqual(second["expected_count"], 1)

    def test_teacher_assignments_progress_by_date(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)

            write_json(tmp / "data" / "student_profiles" / "S001.json", {"student_id": "S001"})
            write_json(tmp / "data" / "assignments" / "A1" / "meta.json", {"assignment_id": "A1", "date": "2026-02-05", "scope": "public"})
            write_json(tmp / "data" / "assignments" / "A2" / "meta.json", {"assignment_id": "A2", "date": "2026-02-05", "scope": "public"})

            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/assignments/progress", params={"date": "2026-02-05"})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["ok"])
                ids = sorted([a.get("assignment_id") for a in data.get("assignments") or []])
                self.assertEqual(ids, ["A1", "A2"])


if __name__ == "__main__":
    unittest.main()
