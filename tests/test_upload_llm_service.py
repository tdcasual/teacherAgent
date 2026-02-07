import unittest
from pathlib import Path

from services.api.upload_llm_service import (
    UploadLlmDeps,
    llm_autofill_requirements,
    llm_parse_assignment_payload,
    llm_parse_exam_scores,
    parse_llm_json,
    summarize_questions_for_prompt,
)


class UploadLlmServiceTest(unittest.TestCase):
    def _deps(self, call_llm):  # type: ignore[no-untyped-def]
        logs = []
        deps = UploadLlmDeps(
            app_root=Path("."),
            call_llm=call_llm,
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
            parse_list_value=lambda value: [x.strip() for x in str(value or "").split(",") if x.strip()],
            compute_requirements_missing=lambda req: [k for k in ("subject", "topic") if not str(req.get(k) or "").strip()],
            merge_requirements=lambda base, update, overwrite=False: {**dict(base), **dict(update)},
            normalize_excel_cell=lambda value: str(value or ""),
        )
        return deps, logs

    def test_parse_llm_json_accepts_fenced_payload(self):
        parsed = parse_llm_json("```json\n{\"intent\":\"assignment\"}\n```")
        self.assertEqual(parsed.get("intent"), "assignment")

    def test_summarize_questions_for_prompt_limits_length(self):
        text = summarize_questions_for_prompt(
            [{"stem": "S" * 1000, "answer": "A" * 1000, "kp": "力学", "difficulty": "basic", "score": 5}],
            limit=120,
        )
        self.assertLessEqual(len(text), 121)

    def test_assignment_parse_returns_error_when_not_json(self):
        deps, _logs = self._deps(
            call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": "not-json"}}]},
        )
        result = llm_parse_assignment_payload("题面", "答案", deps=deps)
        self.assertEqual(result.get("error"), "llm_parse_failed")

    def test_llm_autofill_merges_and_returns_uncertain_missing(self):
        deps, _logs = self._deps(
            call_llm=lambda *_args, **_kwargs: {
                "choices": [
                    {
                        "message": {
                            "content": "{\"requirements\":{\"subject\":\"physics\",\"topic\":\"motion\"},\"uncertain\":[\"topic\"]}"
                        }
                    }
                ]
            },
        )
        merged, missing, ok = llm_autofill_requirements(
            source_text="试卷",
            answer_text="答案",
            questions=[{"stem": "1"}],
            requirements={"subject": "", "topic": ""},
            missing=["subject", "topic"],
            deps=deps,
        )
        self.assertTrue(ok)
        self.assertEqual(merged.get("subject"), "physics")
        self.assertIn("topic", missing)

    def test_llm_parse_exam_scores_extracts_json(self):
        deps, _logs = self._deps(
            call_llm=lambda *_args, **_kwargs: {
                "choices": [{"message": {"content": "{\"mode\":\"total\",\"students\":[]}"}}]
            },
        )
        result = llm_parse_exam_scores("row\tscore", deps=deps)
        self.assertEqual(result.get("mode"), "total")


if __name__ == "__main__":
    unittest.main()
