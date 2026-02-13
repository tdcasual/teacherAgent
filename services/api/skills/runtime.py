from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..dynamic_skill_tools import load_dynamic_tools_for_skill_source
from ..prompt_builder import DEFAULT_PROMPT_VERSION, PROMPTS_DIR
from .spec import SkillModelPolicy, SkillSpec


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


def _read_local_prompt_module(skill: SkillSpec, relpath: str) -> str:
    raw = (relpath or "").strip()
    if not raw:
        return ""

    source = Path(skill.source_path).resolve()
    base = source.parent
    target = (base / raw).resolve()
    if base not in target.parents and target != base:
        raise ValueError(f"invalid local prompt module path: {relpath}")
    if not target.exists():
        raise FileNotFoundError(f"local prompt module not found: {target}")
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
    model_policy: SkillModelPolicy
    dynamic_tools: Dict[str, Dict[str, Any]]

    def apply_tool_policy(self, role_allowed: Set[str]) -> Set[str]:
        allowed = set(role_allowed)
        if self.tools_allow is not None:
            allowed &= set(self.tools_allow)
        if self.tools_deny:
            allowed -= set(self.tools_deny)
        return allowed

    def resolve_model_targets(
        self,
        role_hint: Optional[str],
        kind: Optional[str],
        needs_tools: bool,
        needs_json: bool,
    ) -> List[Dict[str, Any]]:
        policy = self.model_policy
        if not policy.enabled:
            return []

        resolved: List[Dict[str, Any]] = []
        seen: set[tuple] = set()
        role = (role_hint or "").strip()
        kind_value = (kind or "").strip()

        for route in policy.routes:
            match = route.match
            if match.roles and role not in set(match.roles):
                continue
            if match.kinds and kind_value not in set(match.kinds):
                continue
            if match.needs_tools is not None and bool(match.needs_tools) != bool(needs_tools):
                continue
            if match.needs_json is not None and bool(match.needs_json) != bool(needs_json):
                continue
            target = route.target
            key = (target.provider, target.mode, target.model, target.temperature, target.max_tokens)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(
                {
                    "route_id": route.route_id,
                    "provider": target.provider,
                    "mode": target.mode,
                    "model": target.model,
                    "temperature": target.temperature,
                    "max_tokens": target.max_tokens,
                }
            )

        if resolved:
            return resolved

        if policy.default is None:
            return []
        target = policy.default
        return [
            {
                "route_id": "default",
                "provider": target.provider,
                "mode": target.mode,
                "model": target.model,
                "temperature": target.temperature,
                "max_tokens": target.max_tokens,
            }
        ]


def compile_skill_runtime(
    skill: SkillSpec,
    prompt_version: Optional[str] = None,
    debug: Optional[bool] = None,
) -> SkillRuntime:
    version = str(prompt_version or os.getenv("PROMPT_VERSION") or DEFAULT_PROMPT_VERSION)
    parts: List[str] = []

    header = f"激活技能：{skill.skill_id}（{skill.title}）"
    parts.append(header)
    body_text = skill.instructions if skill.instructions else skill.desc
    if body_text:
        parts.append(f"技能说明：{body_text}")

    used_modules: List[str] = []
    for mod in skill.agent.prompt_modules:
        module_name = str(mod or "").strip()
        if not module_name:
            continue
        content = ""
        if module_name.startswith("local:"):
            content = _read_local_prompt_module(skill, module_name[len("local:"):].strip())
        else:
            try:
                content = _read_prompt_module(version, module_name)
            except FileNotFoundError:
                # Markdown-only teacher/claude skills can reference companion files.
                # Keep system skill behavior unchanged: system skills still require
                # prompt modules under prompts/<version>/...
                if skill.source_type in {"teacher", "claude"}:
                    content = _read_local_prompt_module(skill, module_name)
                else:
                    raise
        if not content:
            continue
        used_modules.append(module_name)
        if debug:
            parts.append(f"【SKILL MODULE: {module_name}】\n{content}")
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
        model_policy=skill.agent.model_policy,
        dynamic_tools=load_dynamic_tools_for_skill_source(skill.source_path),
    )
