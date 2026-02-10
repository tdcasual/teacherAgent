import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_longform_service import (
    ExamLongformDeps,
    build_exam_longform_context,
    calc_longform_max_tokens,
    generate_longform_reply,
    summarize_exam_students,
)


class ExamLongformServiceTest(unittest.TestCase):
    def test_summarize_exam_students_returns_error_on_failed_source(self):
        deps = ExamLongformDeps(
            data_dir=Path("/tmp/data"),
            exam_students_list=lambda _exam_id, _limit: {"ok": False, "error": "boom"},
            exam_get=lambda _exam_id: {"ok": False},
            exam_analysis_get=lambda _exam_id: {"ok": False},
            call_llm=lambda *_args, **_kwargs: {},
            non_ws_len=lambda text: len("".join(str(text or "").split())),
        )
        out = summarize_exam_students("EX_ERR", max_total=100, deps=deps)
        self.assertEqual(out.get("error"), "boom")
        self.assertEqual(out.get("exam_id"), "EX_ERR")

    def test_build_exam_longform_context_trims_to_needed_kps(self):
        with TemporaryDirectory() as td:
            data_dir = Path(td) / "data"
            kp_dir = data_dir / "knowledge"
            kp_dir.mkdir(parents=True, exist_ok=True)

            with (kp_dir / "knowledge_points.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["kp_id", "name", "status", "notes"])
                writer.writerow(["KP1", "等效电流", "active", "n1"])
                writer.writerow(["KP2", "欧姆定律", "active", "n2"])
                writer.writerow(["KP3", "电路分析", "active", "n3"])

            with (kp_dir / "knowledge_point_map.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["question_id", "kp_id"])
                writer.writerow(["Q1", "KP1"])
                writer.writerow(["Q2", "KP3"])
                writer.writerow(["Q9", "KP9"])

            deps = ExamLongformDeps(
                data_dir=data_dir,
                exam_students_list=lambda _exam_id, _limit: {
                    "ok": True,
                    "students": [
                        {"student_id": "S1", "total_score": 90},
                        {"student_id": "S2", "total_score": 70},
                    ],
                    "total_students": 2,
                },
                exam_get=lambda exam_id: {
                    "ok": True,
                    "exam_id": exam_id,
                    "generated_at": "2026-02-07T12:00:00",
                    "meta": {"subject": "physics"},
                    "counts": {"students": 2},
                    "totals_summary": {"avg_total": 80},
                    "score_mode": "question_total",
                    "files": {"manifest": "/tmp/data/exams/EX_OK/manifest.json"},
                    "verbose_unused": {"x": 1},
                },
                exam_analysis_get=lambda exam_id: {
                    "ok": True,
                    "exam_id": exam_id,
                    "source": "draft",
                    "analysis": {
                        "totals": {"max_total": 100},
                        "question_metrics": [{"question_id": "Q1"}],
                        "high_loss_questions": [{"question_id": "Q2"}],
                        "knowledge_points": [{"kp_id": "KP2"}],
                    },
                },
                call_llm=lambda *_args, **_kwargs: {},
                non_ws_len=lambda text: len("".join(str(text or "").split())),
            )

            out = build_exam_longform_context("EX_OK", deps=deps)

            overview = out.get("exam_overview") or {}
            self.assertTrue(overview.get("ok"))
            self.assertEqual(overview.get("exam_id"), "EX_OK")
            self.assertNotIn("verbose_unused", overview)
            self.assertEqual(overview.get("files"), {"manifest": "/tmp/data/exams/EX_OK/manifest.json"})

            kp_catalog = out.get("knowledge_points_catalog") or {}
            self.assertEqual(set(kp_catalog.keys()), {"KP1", "KP2", "KP3"})
            q_kp_map = out.get("question_kp_map") or {}
            self.assertEqual(q_kp_map, {"Q1": "KP1", "Q2": "KP3"})

    def test_generate_longform_reply_expands_when_first_response_too_short(self):
        calls = []

        def fake_call_llm(messages, **kwargs):  # type: ignore[no-untyped-def]
            calls.append({"messages": messages, "kwargs": kwargs})
            if len(calls) == 1:
                return {"choices": [{"message": {"content": "短文"}}]}
            return {"choices": [{"message": {"content": "长文" * 1800}}]}

        deps = ExamLongformDeps(
            data_dir=Path("/tmp/data"),
            exam_students_list=lambda _exam_id, _limit: {"ok": True, "students": []},
            exam_get=lambda _exam_id: {"ok": False},
            exam_analysis_get=lambda _exam_id: {"ok": False},
            call_llm=fake_call_llm,
            non_ws_len=lambda text: len("".join(str(text or "").split())),
        )
        convo = [{"role": "system", "content": "S"}]
        out = generate_longform_reply(
            convo,
            min_chars=3000,
            role_hint="teacher",
            skill_id="skill.teacher",
            teacher_id="teacher_1",
            skill_runtime=None,
            deps=deps,
        )

        self.assertGreaterEqual(len(calls), 2)
        self.assertIsNone(calls[0]["kwargs"].get("tools"))
        self.assertEqual(calls[0]["kwargs"].get("kind"), "chat.exam_longform")
        self.assertEqual(len(calls[1]["messages"]), len(convo) + 2)
        self.assertGreaterEqual(len("".join(str(out).split())), 3000)

    def test_calc_longform_max_tokens_is_bounded(self):
        self.assertEqual(calc_longform_max_tokens(1), 2048)
        self.assertEqual(calc_longform_max_tokens(12000), 8192)


if __name__ == "__main__":
    unittest.main()
