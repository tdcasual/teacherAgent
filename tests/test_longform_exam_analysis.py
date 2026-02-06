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


class LongformExamAnalysisTest(unittest.TestCase):
    def test_run_agent_longform_exam_analysis_avoids_tools_and_meets_min_chars(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)

            data_dir = Path(os.environ["DATA_DIR"])
            exam_id = "EX_TEST"
            exam_dir = data_dir / "exams" / exam_id
            derived_dir = exam_dir / "derived"
            derived_dir.mkdir(parents=True, exist_ok=True)

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
                writer.writerow([exam_id, "C1_B", "B", "C1", "Q1", "1", "", "1", "0", "", "0", ""])

            with questions_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"])
                writer.writerow(["Q1", "1", "", "1", "4", ""])

            analysis_dir = data_dir / "analysis" / exam_id
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "draft.json").write_text(
                json.dumps(
                    {
                        "exam_id": exam_id,
                        "generated_at": "2026-02-05T00:00:00",
                        "totals": {"student_count": 2, "max_total": 4.0, "avg_total": 2.0, "median_total": 2.0},
                        "knowledge_points": [],
                        "high_loss_questions": [],
                        "question_metrics": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = {
                "exam_id": exam_id,
                "generated_at": "2026-02-05T00:00:00",
                "files": {
                    "responses_scored": str(responses_path.resolve()),
                    "questions": str(questions_path.resolve()),
                },
                "counts": {"students": 2, "responses": 2, "questions": 1},
            }
            (exam_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            calls = {"count": 0}

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):  # type: ignore[no-untyped-def]
                self.assertIsNone(tools, "longform path should not provide tools to the model")
                calls["count"] += 1
                return {"choices": [{"message": {"content": ("长文" * 1600)}}]}

            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]

            result = app_mod.run_agent(
                [{"role": "user", "content": f"查看{exam_id}的考试分析，要求字数不少于3000字"}],
                role_hint="teacher",
            )
            text = result.get("reply") or ""
            self.assertGreaterEqual(app_mod._non_ws_len(text), 3000)
            self.assertEqual(calls["count"], 1)

    def test_run_agent_tool_budget_exhausted_falls_back_to_no_tool_answer(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)

            def fake_tool_dispatch(name, args, role=None):  # type: ignore[no-untyped-def]
                return {"ok": True, "tool": name}

            app_mod.tool_dispatch = fake_tool_dispatch  # type: ignore[attr-defined]

            def fake_call_llm(messages, tools=None, role_hint=None, max_tokens=None, **kwargs):  # type: ignore[no-untyped-def]
                # When tools are present, keep asking for too many tools; when tools are absent, provide final answer.
                if tools:
                    tool_calls = []
                    for idx in range(13):  # exceed CHAT_MAX_TOOL_CALLS=12
                        tool_calls.append(
                            {
                                "id": f"call_{idx}",
                                "type": "function",
                                "function": {"name": "exam.list", "arguments": "{}"},
                            }
                        )
                    return {"choices": [{"message": {"content": "", "tool_calls": tool_calls}}]}
                return {"choices": [{"message": {"content": "final_no_tool_answer"}}]}

            app_mod.call_llm = fake_call_llm  # type: ignore[attr-defined]

            result = app_mod.run_agent(
                [{"role": "user", "content": "列出考试"}],
                role_hint="teacher",
            )
            self.assertEqual(result.get("reply"), "final_no_tool_answer")


if __name__ == "__main__":
    unittest.main()
