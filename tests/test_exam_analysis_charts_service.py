import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_analysis_charts_service import (
    ExamAnalysisChartsDeps,
    build_exam_chart_bundle_input,
    exam_analysis_charts_generate,
    normalize_exam_chart_types,
)


class ExamAnalysisChartsServiceTest(unittest.TestCase):
    def _deps(
        self,
        root: Path,
        responses_path: Path,
        questions_path: Path,
        execute_chart_exec_fn,  # type: ignore[no-untyped-def]
    ) -> ExamAnalysisChartsDeps:
        def safe_int_arg(value, default, minimum, maximum):  # type: ignore[no-untyped-def]
            try:
                out = int(value)
            except Exception:
                out = default
            return max(minimum, min(maximum, out))

        def parse_score(value):  # type: ignore[no-untyped-def]
            try:
                text = str(value).strip()
                if not text:
                    return None
                return float(text)
            except Exception:
                return None

        return ExamAnalysisChartsDeps(
            app_root=root,
            uploads_dir=root / "uploads",
            safe_int_arg=safe_int_arg,
            load_exam_manifest=lambda _exam_id: {"ok": True},
            exam_responses_path=lambda _manifest: responses_path,
            compute_exam_totals=lambda _path: {
                "totals": {"S1": 270.0, "S2": 235.0, "S3": 190.0, "S4": 155.0},
                "students": {
                    "S1": {"class_name": "C1"},
                    "S2": {"class_name": "C1"},
                    "S3": {"class_name": "C2"},
                    "S4": {"class_name": "C2"},
                },
            },
            exam_analysis_get=lambda _exam_id: {
                "ok": True,
                "analysis": {
                    "knowledge_points": [
                        {"kp_id": "KP-A", "loss_rate": 0.2, "coverage_count": 3},
                        {"kp_id": "KP-B", "loss_rate": 0.5, "coverage_count": 3},
                    ]
                },
            },
            parse_score_value=parse_score,
            exam_questions_path=lambda _manifest: questions_path,
            read_questions_csv=lambda _path: {
                "Q1": {"question_id": "Q1", "question_no": "1", "max_score": "100"},
                "Q2": {"question_id": "Q2", "question_no": "2", "max_score": "100"},
                "Q3": {"question_id": "Q3", "question_no": "3", "max_score": "100"},
            },
            execute_chart_exec=execute_chart_exec_fn,
        )

    def test_normalize_chart_types_supports_alias_and_default(self):
        self.assertEqual(
            normalize_exam_chart_types(["分布", "区分度"]),
            ["score_distribution", "question_discrimination"],
        )
        self.assertEqual(
            normalize_exam_chart_types(None),
            ["score_distribution", "knowledge_radar", "class_compare", "question_discrimination"],
        )

    def test_build_bundle_returns_error_when_exam_missing(self):
        deps = ExamAnalysisChartsDeps(
            app_root=Path("/tmp/app"),
            uploads_dir=Path("/tmp/uploads"),
            safe_int_arg=lambda value, default, minimum, maximum: default,
            load_exam_manifest=lambda _exam_id: {},
            exam_responses_path=lambda _manifest: None,
            compute_exam_totals=lambda _path: {},
            exam_analysis_get=lambda _exam_id: {},
            parse_score_value=lambda _value: None,
            exam_questions_path=lambda _manifest: None,
            read_questions_csv=lambda _path: {},
            execute_chart_exec=lambda _args, app_root, uploads_dir: {},
        )
        out = build_exam_chart_bundle_input("EX404", top_n=8, deps=deps)
        self.assertEqual(out.get("error"), "exam_not_found")
        self.assertEqual(out.get("exam_id"), "EX404")

    def test_generate_subset_charts_succeeds(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            responses_path = data_dir / "responses_scored.csv"
            questions_path = data_dir / "questions.csv"

            with responses_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["student_id", "student_name", "class_name", "question_id", "question_no", "score"])
                rows = [
                    ("S1", "A", "C1", "Q1", "1", "95"),
                    ("S1", "A", "C1", "Q2", "2", "90"),
                    ("S1", "A", "C1", "Q3", "3", "85"),
                    ("S2", "B", "C1", "Q1", "1", "80"),
                    ("S2", "B", "C1", "Q2", "2", "75"),
                    ("S2", "B", "C1", "Q3", "3", "70"),
                    ("S3", "C", "C2", "Q1", "1", "70"),
                    ("S3", "C", "C2", "Q2", "2", "65"),
                    ("S3", "C", "C2", "Q3", "3", "60"),
                    ("S4", "D", "C2", "Q1", "1", "60"),
                    ("S4", "D", "C2", "Q2", "2", "55"),
                    ("S4", "D", "C2", "Q3", "3", "50"),
                ]
                writer.writerows(rows)

            with questions_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["question_id", "question_no", "max_score"])
                writer.writerow(["Q1", "1", "100"])
                writer.writerow(["Q2", "2", "100"])
                writer.writerow(["Q3", "3", "100"])

            calls = []

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                calls.append(args)
                run_id = f"run_{len(calls)}"
                save_as = str(args.get("save_as") or "main.png")
                return {
                    "ok": True,
                    "run_id": run_id,
                    "image_url": f"/charts/{run_id}/{save_as}",
                    "meta_url": f"/chart-runs/{run_id}/meta",
                    "artifacts": [],
                }

            deps = self._deps(root, responses_path, questions_path, fake_execute)
            out = exam_analysis_charts_generate(
                {"exam_id": "EX1", "chart_types": ["分布", "对比"], "top_n": 6},
                deps=deps,
            )

            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("generated_count"), 2)
            self.assertEqual(len(calls), 2)
            self.assertEqual(out.get("chart_types_requested"), ["score_distribution", "class_compare"])
            self.assertIn("/charts/", str(out.get("markdown") or ""))


if __name__ == "__main__":
    unittest.main()
