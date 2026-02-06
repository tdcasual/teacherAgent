from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

from ..prompt_builder import DEFAULT_PROMPT_VERSION, PROMPTS_DIR
from .spec import SkillSpec


def _read_prompt_module(version: str, relpath: str) -> str:
    raw = (relpath or "").strip()
    if not raw:
        return ""

    base = (PROMPTS_DIR / version).resolve()

    # Allow both:
    # - "teacher/skills/teacher_ops.md" (version-relative)
    # - "prompts/v1/teacher/skills/teacher_ops.md" (repo-relative-ish)
    parts = Path(raw).parts
    if parts and parts[0] == "prompts":
        # prompts/<version>/<...>
        if len(parts) >= 3 and parts[1] == version:
            raw = str(Path(*parts[2:]))
        elif len(parts) >= 2:
            # prompts/<...> (treat as relative to PROMPTS_DIR)
            candidate = (PROMPTS_DIR / Path(*parts[1:])).resolve()
            if base not in candidate.parents and candidate != base:
                raise ValueError(f"invalid prompt module path: {relpath}")
            return candidate.read_text(encoding="utf-8").strip()

    # Also accept "<version>/<...>".
    parts2 = Path(raw).parts
    if parts2 and parts2[0] == version and len(parts2) >= 2:
        raw = str(Path(*parts2[1:]))

    target = (base / raw).resolve()
    # Prevent path traversal.
    if base not in target.parents and target != base:
        raise ValueError(f"invalid prompt module path: {relpath}")
    if not target.exists():
        raise FileNotFoundError(f"prompt module not found: {target}")
    return target.read_text(encoding="utf-8").strip()


@dataclass(frozen=True)
class SkillRuntime:
    skill: SkillSpec
    system_prompt: str
    tools_allow: Optional[List[str]]
    tools_deny: List[str]
    max_tool_rounds: Optional[int]
    max_tool_calls: Optional[int]
    context_providers: List[str]

    def apply_tool_policy(self, role_allowed: Set[str]) -> Set[str]:
        allowed = set(role_allowed)
        if self.tools_allow is not None:
            allowed &= set(self.tools_allow)
        if self.tools_deny:
            allowed -= set(self.tools_deny)
        return allowed


def compile_skill_runtime(
    skill: SkillSpec,
    prompt_version: Optional[str] = None,
    debug: Optional[bool] = None,
) -> SkillRuntime:
    version = prompt_version or os.getenv("PROMPT_VERSION", DEFAULT_PROMPT_VERSION)
    parts: List[str] = []

    header = f"激活技能：{skill.skill_id}（{skill.title}）"
    parts.append(header)
    if skill.desc:
        parts.append(f"技能说明：{skill.desc}")

    used_modules: List[str] = []
    for mod in skill.agent.prompt_modules:
        content = _read_prompt_module(version, mod)
        if not content:
            continue
        used_modules.append(mod)
        if debug:
            parts.append(f"【SKILL MODULE: {mod}】\n{content}")
        else:
            parts.append(content)

    system_prompt = "\n\n".join([p for p in parts if p]).strip()
    if system_prompt:
        system_prompt += "\n"

    return SkillRuntime(
        skill=skill,
        system_prompt=system_prompt,
        tools_allow=skill.agent.tools.allow,
        tools_deny=skill.agent.tools.deny,
        max_tool_rounds=skill.agent.budgets.max_tool_rounds,
        max_tool_calls=skill.agent.budgets.max_tool_calls,
        context_providers=skill.agent.context_providers,
    )

