import json
import unittest
from pathlib import Path

from services.api.assignment_intent_service import detect_assignment_intent
from services.api.skill_auto_router import resolve_effective_skill

APP_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = APP_ROOT / "tests" / "fixtures" / "teacher_workflow_routing_cases.json"


class TeacherWorkflowRoutingRegressionTest(unittest.TestCase):
    def test_teacher_fixture_cases_are_stable(self):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cases = payload.get("cases") or []
        self.assertGreaterEqual(len(cases), 20)
        self.assertLessEqual(len(cases), 30)

        for case in cases:
            with self.subTest(case=case.get("name")):
                result = resolve_effective_skill(
                    app_root=APP_ROOT,
                    role_hint=case.get("role_hint") or "teacher",
                    requested_skill_id=case.get("requested_skill_id") or "",
                    last_user_text=case.get("last_user_text") or "",
                    detect_assignment_intent=detect_assignment_intent,
                )
                self.assertEqual(result.get("effective_skill_id"), case.get("expected_skill_id"))
                self.assertEqual(result.get("reason"), case.get("expected_reason"))
                self.assertGreaterEqual(
                    float(result.get("confidence") or 0.0),
                    float(case.get("min_confidence") or 0.0),
                )

                expected_candidate = str(case.get("first_candidate_skill_id") or "").strip()
                candidates = result.get("candidates") or []
                if expected_candidate:
                    self.assertTrue(candidates)
                    self.assertEqual(candidates[0].get("skill_id"), expected_candidate)
                if case.get("expect_candidates_empty"):
                    self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
