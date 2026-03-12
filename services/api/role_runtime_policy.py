from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .skills.router import default_skill_id_for_role


@dataclass(frozen=True)
class RoleRuntimePolicy:
    role: str
    default_skill_id: str
    default_session_id: Optional[str]
    supports_workflow_explanation: bool
    supports_memory_proposals: bool
    uses_teacher_model_config: bool
    limiter_kind: str


def get_role_runtime_policy(role_hint: Optional[str]) -> RoleRuntimePolicy:
    role = str(role_hint or '').strip().lower()
    if role == 'teacher':
        return RoleRuntimePolicy(
            role='teacher',
            default_skill_id=default_skill_id_for_role('teacher'),
            default_session_id='main',
            supports_workflow_explanation=True,
            supports_memory_proposals=True,
            uses_teacher_model_config=True,
            limiter_kind='teacher',
        )
    if role == 'student':
        return RoleRuntimePolicy(
            role='student',
            default_skill_id=default_skill_id_for_role('student'),
            default_session_id=None,
            supports_workflow_explanation=False,
            supports_memory_proposals=True,
            uses_teacher_model_config=False,
            limiter_kind='student',
        )
    return RoleRuntimePolicy(
        role=role or 'unknown',
        default_skill_id=default_skill_id_for_role(role_hint),
        default_session_id=None,
        supports_workflow_explanation=False,
        supports_memory_proposals=False,
        uses_teacher_model_config=False,
        limiter_kind='default',
    )
