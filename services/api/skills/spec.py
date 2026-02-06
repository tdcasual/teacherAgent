from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return []


def _as_int_opt(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        iv = int(str(value).strip())
    except Exception:
        return None
    return iv


@dataclass(frozen=True)
class SkillToolsPolicy:
    # None means: inherit role default tools (no allowlist restriction).
    allow: Optional[List[str]]
    deny: List[str]


@dataclass(frozen=True)
class SkillBudgets:
    max_tool_rounds: Optional[int]
    max_tool_calls: Optional[int]


@dataclass(frozen=True)
class SkillAgentSpec:
    prompt_modules: List[str]
    context_providers: List[str]
    tools: SkillToolsPolicy
    budgets: SkillBudgets


@dataclass(frozen=True)
class SkillUiSpec:
    prompts: List[str]
    examples: List[str]


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    schema_version: int
    title: str
    desc: str
    allowed_roles: List[str]
    ui: SkillUiSpec
    agent: SkillAgentSpec
    source_path: str

    def as_public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.skill_id,
            "schema_version": self.schema_version,
            "title": self.title,
            "desc": self.desc,
            "allowed_roles": self.allowed_roles,
            "prompts": self.ui.prompts,
            "examples": self.ui.examples,
            "agent": {
                "prompt_modules": self.agent.prompt_modules,
                "context_providers": self.agent.context_providers,
                "tools": {"allow": self.agent.tools.allow, "deny": self.agent.tools.deny},
                "budgets": {
                    "max_tool_rounds": self.agent.budgets.max_tool_rounds,
                    "max_tool_calls": self.agent.budgets.max_tool_calls,
                },
            },
        }


def parse_skill_spec(skill_id: str, source_path: str, raw: Dict[str, Any]) -> SkillSpec:
    schema_version = _as_int_opt(raw.get("schema_version")) or _as_int_opt(raw.get("schemaVersion")) or 1

    title = str(raw.get("title") or raw.get("display_name") or raw.get("displayName") or "").strip() or "未命名技能"
    desc = str(raw.get("desc") or raw.get("description") or "").strip()
    allowed_roles = _as_str_list(raw.get("allowed_roles") or raw.get("allowedRoles"))

    ui_raw = raw.get("ui") if isinstance(raw.get("ui"), dict) else {}
    ui_prompts = _as_str_list(ui_raw.get("prompts") if isinstance(ui_raw, dict) else raw.get("prompts"))
    ui_examples = _as_str_list(ui_raw.get("examples") if isinstance(ui_raw, dict) else raw.get("examples"))
    ui = SkillUiSpec(prompts=ui_prompts, examples=ui_examples)

    agent_raw = raw.get("agent") if isinstance(raw.get("agent"), dict) else {}
    prompt_modules = _as_str_list(agent_raw.get("prompt_modules") or agent_raw.get("promptModules"))
    context_providers = _as_str_list(agent_raw.get("context_providers") or agent_raw.get("contextProviders"))

    tools_raw = agent_raw.get("tools") if isinstance(agent_raw.get("tools"), dict) else {}
    allow_value = tools_raw.get("allow") if isinstance(tools_raw, dict) else None
    allow_list = _as_str_list(allow_value) if allow_value is not None else None
    deny_list = _as_str_list(tools_raw.get("deny") if isinstance(tools_raw, dict) else None)
    tools = SkillToolsPolicy(allow=allow_list, deny=deny_list)

    budgets_raw = agent_raw.get("budgets") if isinstance(agent_raw.get("budgets"), dict) else {}
    budgets = SkillBudgets(
        max_tool_rounds=_as_int_opt(budgets_raw.get("max_tool_rounds") if isinstance(budgets_raw, dict) else None),
        max_tool_calls=_as_int_opt(budgets_raw.get("max_tool_calls") if isinstance(budgets_raw, dict) else None),
    )

    agent = SkillAgentSpec(
        prompt_modules=prompt_modules,
        context_providers=context_providers,
        tools=tools,
        budgets=budgets,
    )

    return SkillSpec(
        skill_id=skill_id,
        schema_version=int(schema_version),
        title=title,
        desc=desc,
        allowed_roles=allowed_roles,
        ui=ui,
        agent=agent,
        source_path=source_path,
    )

