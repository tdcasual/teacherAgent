import unittest
from pathlib import Path

from services.api.assignment_generate_tool_service import (
    AssignmentGenerateToolDeps,
    assignment_generate,
)


class AssignmentGenerateToolServiceTest(unittest.TestCase):
    def _deps(self):
        captured = {"cmd": None, "logs": []}

        def _run_script(cmd):
            captured["cmd"] = list(cmd)
            return "done"

        deps = AssignmentGenerateToolDeps(
            app_root=Path("/repo"),
            parse_date_str=lambda value: str(value or "2026-02-08"),
            ensure_requirements_for_assignment=lambda *_args: {"ok": True},
            run_script=_run_script,
            postprocess_assignment_meta=lambda *_args, **_kwargs: None,
            diag_log=lambda event, payload=None: captured["logs"].append((event, payload or {})),
        )
        return deps, captured

    def test_validation_error_is_returned(self):
        deps, _captured = self._deps()
        deps = AssignmentGenerateToolDeps(
            **{
                **deps.__dict__,
                "ensure_requirements_for_assignment": lambda *_args: {"error": "missing_requirements"},
            }
        )

        result = assignment_generate({"assignment_id": "HW_1"}, deps=deps)

        self.assertEqual(result.get("error"), "missing_requirements")

    def test_success_builds_command_and_tolerates_postprocess_failure(self):
        deps, captured = self._deps()
        deps = AssignmentGenerateToolDeps(
            **{
                **deps.__dict__,
                "postprocess_assignment_meta": lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            }
        )

        result = assignment_generate(
            {
                "assignment_id": "HW_1",
                "kp": "力学",
                "question_ids": "Q1,Q2",
                "mode": "auto",
                "date": "2026-02-08",
                "class_name": "高二2403班",
                "student_ids": "S1",
                "source": "teacher",
                "per_kp": 3,
                "core_examples": "EX_A",
                "generate": True,
            },
            deps=deps,
        )

        self.assertEqual(result.get("ok"), True)
        cmd = captured["cmd"]
        self.assertIn("--assignment-id", cmd)
        self.assertIn("HW_1", cmd)
        self.assertIn("--generate", cmd)
        self.assertEqual(captured["logs"][0][0], "assignment.meta.postprocess_failed")


if __name__ == "__main__":
    unittest.main()
