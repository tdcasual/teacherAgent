from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from .loader import LoadedSkills
from .spec import SkillSpec


_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")


def default_skill_id_for_role(role_hint: Optional[str]) -> str:
    if role_hint == "student":
        return "physics-student-coach"
    if role_hint == "teacher":
        return "physics-teacher-ops"
    return "physics-teacher-ops"


@dataclass(frozen=True)
class SkillSelection:
    skill: Optional[SkillSpec]
    warning: str


def resolve_skill(
    loaded: LoadedSkills,
    requested_skill_id: Optional[str],
    role_hint: Optional[str],
) -> SkillSelection:
    warning = ""
    skill_id = (requested_skill_id or "").strip()
    if skill_id and not _SKILL_ID_RE.match(skill_id):
        warning = "invalid skill_id; fell back to default skill."
        skill_id = ""

    if not skill_id:
        skill_id = default_skill_id_for_role(role_hint)

    skill = loaded.skills.get(skill_id)
    if not skill:
        fallback = default_skill_id_for_role(role_hint)
        skill = loaded.skills.get(fallback)
        if skill:
            warning = warning or f"skill not found: {skill_id}; fell back to {fallback}."
        else:
            warning = warning or f"skill not found: {skill_id}; no fallback available."
            return SkillSelection(skill=None, warning=warning)

    # Role gate.
    if role_hint and skill.allowed_roles and role_hint not in skill.allowed_roles:
        fallback = default_skill_id_for_role(role_hint)
        fallback_skill = loaded.skills.get(fallback)
        if fallback_skill and (not fallback_skill.allowed_roles or role_hint in fallback_skill.allowed_roles):
            warning = warning or f"skill {skill.skill_id} not allowed for role={role_hint}; fell back to {fallback}."
            return SkillSelection(skill=fallback_skill, warning=warning)
        warning = warning or f"skill {skill.skill_id} not allowed for role={role_hint}."
        return SkillSelection(skill=None, warning=warning)

    return SkillSelection(skill=skill, warning=warning)

