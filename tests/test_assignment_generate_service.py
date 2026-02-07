import unittest
from pathlib import Path

from services.api.assignment_generate_service import (
    AssignmentGenerateDeps,
    AssignmentGenerateError,
    generate_assignment,
)


class AssignmentGenerateServiceTest(unittest.TestCase):
    def _deps(self):
        captured = {"args": None, "log": []}

        def _run_script(args):
            captured["args"] = list(args)
            return "ok"

        deps = AssignmentGenerateDeps(
            app_root=Path("/repo"),
            parse_date_str=lambda value: str(value or "2026-02-08"),
            ensure_requirements_for_assignment=lambda *_args: {"ok": True},
            run_script=_run_script,
            postprocess_assignment_meta=lambda *_args, **_kwargs: None,
            diag_log=lambda event, payload=None: captured["log"].append((event, payload or {})),
        )
        return deps, captured

    def test_invalid_requirements_json_raises_400(self):
        deps, _captured = self._deps()

        with self.assertRaises(AssignmentGenerateError) as cm:
            generate_assignment(
                assignment_id="HW_1",
                kp="",
                question_ids="",
                per_kp=5,
                core_examples="",
                generate=False,
                mode="",
                date="2026-02-08",
                due_at="",
                class_name="",
                student_ids="",
                source="",
                requirements_json="{bad-json",
                deps=deps,
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "requirements_json is not valid JSON")

    def test_requirements_error_raises_400(self):
        deps, _captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{
                **deps.__dict__,
                "ensure_requirements_for_assignment": lambda *_args: {"error": "missing_requirements"},
            }
        )

        with self.assertRaises(AssignmentGenerateError) as cm:
            generate_assignment(
                assignment_id="HW_1",
                kp="",
                question_ids="",
                per_kp=5,
                core_examples="",
                generate=False,
                mode="",
                date="2026-02-08",
                due_at="",
                class_name="",
                student_ids="",
                source="teacher",
                requirements_json=None,
                deps=deps,
            )

        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail.get("error"), "missing_requirements")

    def test_success_builds_command_and_logs_postprocess_error(self):
        deps, captured = self._deps()
        deps = AssignmentGenerateDeps(
            **{
                **deps.__dict__,
                "postprocess_assignment_meta": lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            }
        )

        result = generate_assignment(
            assignment_id="HW_1",
            kp="力学",
            question_ids="Q1,Q2",
            per_kp=3,
            core_examples="EX_A",
            generate=True,
            mode="auto",
            date="2026-02-08",
            due_at="2026-02-09T20:00:00",
            class_name="高二2403班",
            student_ids="S1,S2",
            source="teacher",
            requirements_json='{"core_concepts":["力"]}',
            deps=deps,
        )

        self.assertEqual(result.get("ok"), True)
        args = captured["args"]
        self.assertIn("--assignment-id", args)
        self.assertIn("HW_1", args)
        self.assertIn("--kp", args)
        self.assertIn("力学", args)
        self.assertIn("--generate", args)
        self.assertEqual(captured["log"][0][0], "assignment.meta.postprocess_failed")


if __name__ == "__main__":
    unittest.main()
