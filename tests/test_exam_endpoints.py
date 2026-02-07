import csv
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


class ExamEndpointsTest(unittest.TestCase):
    def test_exam_routes_use_exam_api_service_deps(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            client = TestClient(app_mod.app)
            sentinel = object()
            captured = {}

            def _fake_impl(exam_id: str, *, deps):
                captured["exam_id"] = exam_id
                captured["deps"] = deps
                return {"ok": True, "exam_id": exam_id}

            app_mod._get_exam_detail_api_impl = _fake_impl
            app_mod._exam_api_deps = lambda: sentinel

            res = client.get("/exam/E1")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(captured.get("exam_id"), "E1")
            self.assertIs(captured.get("deps"), sentinel)

    def test_exam_endpoints_from_manifest(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            client = TestClient(app_mod.app)

            data_dir = Path(os.environ["DATA_DIR"])
            exam_id = "EX_TEST"
            exam_dir = data_dir / "exams" / exam_id
            derived_dir = exam_dir / "derived"
            derived_dir.mkdir(parents=True, exist_ok=True)

            # Derived responses/questions
            responses_path = derived_dir / "responses_scored.csv"
            questions_path = derived_dir / "questions.csv"

            with responses_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "exam_id",
                        "student_id",
                        "student_name",
                        "class_name",
                        "question_id",
                        "question_no",
                        "sub_no",
                        "raw_label",
                        "raw_value",
                        "raw_answer",
                        "score",
                        "is_correct",
                    ]
                )
                writer.writerow([exam_id, "C1_A", "A", "C1", "Q1", "1", "", "1", "4", "", "4", ""])
                writer.writerow([exam_id, "C1_A", "A", "C1", "Q2", "2", "", "2", "3", "", "3", ""])
                writer.writerow([exam_id, "C1_B", "B", "C1", "Q1", "1", "", "1", "2", "", "2", ""])
                writer.writerow([exam_id, "C1_B", "B", "C1", "Q2", "2", "", "2", "1", "", "1", ""])

            with questions_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
                writer.writerow(["Q1", "1", "", "1", "4", ""])
                writer.writerow(["Q2", "2", "", "2", "4", ""])

            # Analysis draft (fallback path)
            analysis_dir = data_dir / "analysis" / exam_id
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "draft.json").write_text(
                json.dumps({"exam_id": exam_id, "generated_at": "2026-02-05T00:00:00", "totals": {}}, ensure_ascii=False),
                encoding="utf-8",
            )

            manifest = {
                "exam_id": exam_id,
                "generated_at": "2026-02-05T00:00:00",
                "files": {
                    # Use absolute paths so resolve_manifest_path works with temp dirs.
                    "responses_scored": str(responses_path.resolve()),
                    "questions": str(questions_path.resolve()),
                },
                "counts": {"students": 2, "responses": 4, "questions": 2},
            }
            (exam_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            res = client.get(f"/exam/{exam_id}")
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["exam_id"], exam_id)
            self.assertEqual(payload["counts"]["students"], 2)
            self.assertEqual(payload["counts"]["questions"], 2)

            res = client.get(f"/exam/{exam_id}/analysis")
            self.assertEqual(res.status_code, 200)
            analysis = res.json()
            self.assertTrue(analysis["ok"])
            self.assertEqual(analysis["exam_id"], exam_id)

            res = client.get(f"/exam/{exam_id}/students", params={"limit": 10})
            self.assertEqual(res.status_code, 200)
            students = res.json()
            self.assertTrue(students["ok"])
            self.assertEqual(students["total_students"], 2)
            self.assertEqual(len(students["students"]), 2)

            res = client.get(f"/exam/{exam_id}/student/C1_A")
            self.assertEqual(res.status_code, 200)
            student = res.json()
            self.assertTrue(student["ok"])
            self.assertEqual(student["student"]["student_id"], "C1_A")

            res = client.get(f"/exam/{exam_id}/question/Q1")
            self.assertEqual(res.status_code, 200)
            q = res.json()
            self.assertTrue(q["ok"])
            self.assertEqual(q["question"]["question_id"], "Q1")

            range_rank = app_mod.tool_dispatch(
                "exam.range.top_students",
                {"exam_id": exam_id, "start_question_no": 1, "end_question_no": 2, "top_n": 2},
                role="teacher",
            )
            self.assertTrue(range_rank["ok"])
            self.assertEqual(range_rank["summary"]["max_score"], 7.0)
            self.assertEqual(range_rank["summary"]["min_score"], 3.0)
            self.assertEqual(range_rank["top_students"][0]["student_id"], "C1_A")
            self.assertEqual(range_rank["bottom_students"][0]["student_id"], "C1_B")

            range_batch = app_mod.tool_dispatch(
                "exam.range.summary.batch",
                {
                    "exam_id": exam_id,
                    "ranges": [
                        {"label": "Q1 only", "start_question_no": 1, "end_question_no": 1},
                        {"label": "Q1-Q2", "start_question_no": 1, "end_question_no": 2},
                    ],
                    "top_n": 2,
                },
                role="teacher",
            )
            self.assertTrue(range_batch["ok"])
            self.assertEqual(range_batch["range_count_requested"], 2)
            self.assertEqual(range_batch["range_count_succeeded"], 2)
            self.assertEqual(range_batch["ranges"][0]["summary"]["max_score"], 4.0)
            self.assertEqual(range_batch["ranges"][1]["summary"]["max_score"], 7.0)

            question_batch = app_mod.tool_dispatch(
                "exam.question.batch.get",
                {"exam_id": exam_id, "question_nos": [1, 2], "top_n": 1},
                role="teacher",
            )
            self.assertTrue(question_batch["ok"])
            self.assertEqual(question_batch["question_count_succeeded"], 2)
            self.assertEqual(question_batch["question_count_failed"], 0)
            self.assertEqual(len(question_batch["questions"][0]["sample_top_students"]), 1)


if __name__ == "__main__":
    unittest.main()
