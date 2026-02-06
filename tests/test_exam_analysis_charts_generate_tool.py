import csv
import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def prepare_exam_fixture(tmp_dir: Path, exam_id: str = "EX_TEST") -> None:
    data_dir = tmp_dir / "data"
    staging_dir = data_dir / "staging"
    exams_dir = data_dir / "exams" / exam_id
    analysis_dir = data_dir / "analysis" / exam_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    exams_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    responses_path = staging_dir / "responses_scored.csv"
    with responses_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        rows = [
            ("S1", "张一", "C1", 95, 90, 100),
            ("S2", "张二", "C1", 75, 60, 80),
            ("S3", "李三", "C2", 65, 70, 60),
            ("S4", "李四", "C2", 45, 35, 55),
        ]
        for sid, name, cls, q1, q2, q3 in rows:
            for qid, qno, score in (("Q1", "1", q1), ("Q2", "2", q2), ("Q3", "3", q3)):
                writer.writerow(
                    {
                        "exam_id": exam_id,
                        "student_id": sid,
                        "student_name": name,
                        "class_name": cls,
                        "question_id": qid,
                        "question_no": qno,
                        "sub_no": "",
                        "raw_label": qno,
                        "raw_value": "",
                        "raw_answer": "",
                        "score": str(score),
                        "is_correct": "",
                    }
                )

    questions_path = staging_dir / "questions.csv"
    with questions_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
        writer.writeheader()
        writer.writerow({"question_id": "Q1", "question_no": "1", "sub_no": "", "order": "1", "max_score": "100", "stem_ref": ""})
        writer.writerow({"question_id": "Q2", "question_no": "2", "sub_no": "", "order": "2", "max_score": "100", "stem_ref": ""})
        writer.writerow({"question_id": "Q3", "question_no": "3", "sub_no": "", "order": "3", "max_score": "100", "stem_ref": ""})

    draft_path = analysis_dir / "draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "exam_id": exam_id,
                "generated_at": "2026-02-06T00:00:00",
                "knowledge_points": [
                    {"kp_id": "KP-A", "loss_rate": 0.20, "coverage_count": 2, "coverage_score": 100, "avg_score": 80},
                    {"kp_id": "KP-B", "loss_rate": 0.45, "coverage_count": 2, "coverage_score": 100, "avg_score": 55},
                    {"kp_id": "KP-C", "loss_rate": 0.60, "coverage_count": 1, "coverage_score": 100, "avg_score": 40},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = {
        "exam_id": exam_id,
        "generated_at": "2026-02-06T00:00:00",
        "files": {
            "responses": str(responses_path),
            "questions": str(questions_path),
            "analysis_draft_json": str(draft_path),
        },
        "counts": {"students": 4, "responses": 12},
    }
    (exams_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


class ExamAnalysisChartsGenerateToolTest(unittest.TestCase):
    def test_generate_default_bundle(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            prepare_exam_fixture(tmp)
            app_mod = load_app(tmp)

            calls = []

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                calls.append(args)
                idx = len(calls)
                run_id = f"chr_test_{idx}"
                save_as = str(args.get("save_as") or "main.png")
                return {
                    "ok": True,
                    "run_id": run_id,
                    "image_url": f"/charts/{run_id}/{save_as}",
                    "meta_url": f"/chart-runs/{run_id}/meta",
                    "artifacts": [{"name": save_as, "url": f"/charts/{run_id}/{save_as}", "size": 1234}],
                }

            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]
            res = app_mod.tool_dispatch("exam.analysis.charts.generate", {"exam_id": "EX_TEST"}, role="teacher")

            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("generated_count"), 4)
            self.assertEqual(len(calls), 4)
            self.assertIn("/charts/", res.get("markdown", ""))
            self.assertIn("score_distribution", set(res.get("chart_types_requested") or []))

    def test_generate_subset_by_alias(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            prepare_exam_fixture(tmp)
            app_mod = load_app(tmp)

            calls = []

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                calls.append(args)
                idx = len(calls)
                run_id = f"chr_test_{idx}"
                save_as = str(args.get("save_as") or "main.png")
                return {"ok": True, "run_id": run_id, "image_url": f"/charts/{run_id}/{save_as}", "meta_url": f"/chart-runs/{run_id}/meta"}

            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]
            res = app_mod.tool_dispatch(
                "exam.analysis.charts.generate",
                {"exam_id": "EX_TEST", "chart_types": ["分布", "区分度"], "top_n": 6},
                role="teacher",
            )

            self.assertTrue(res.get("ok"))
            requested = list(res.get("chart_types_requested") or [])
            self.assertEqual(requested, ["score_distribution", "question_discrimination"])
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
