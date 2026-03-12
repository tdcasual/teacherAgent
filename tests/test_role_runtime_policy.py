from __future__ import annotations

import unittest

from services.api.role_runtime_policy import get_role_runtime_policy


class RoleRuntimePolicyTest(unittest.TestCase):
    def test_teacher_policy_fields_are_stable(self):
        policy = get_role_runtime_policy('teacher')
        self.assertEqual(policy.role, 'teacher')
        self.assertEqual(policy.default_skill_id, 'physics-teacher-ops')
        self.assertEqual(policy.default_session_id, 'main')
        self.assertTrue(policy.supports_workflow_explanation)
        self.assertTrue(policy.supports_memory_proposals)
        self.assertTrue(policy.uses_teacher_model_config)
        self.assertEqual(policy.limiter_kind, 'teacher')

    def test_student_policy_fields_are_stable(self):
        policy = get_role_runtime_policy('student')
        self.assertEqual(policy.role, 'student')
        self.assertEqual(policy.default_skill_id, 'physics-student-coach')
        self.assertIsNone(policy.default_session_id)
        self.assertFalse(policy.supports_workflow_explanation)
        self.assertTrue(policy.supports_memory_proposals)
        self.assertFalse(policy.uses_teacher_model_config)
        self.assertEqual(policy.limiter_kind, 'student')


if __name__ == '__main__':
    unittest.main()
