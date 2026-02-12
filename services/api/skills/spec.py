from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _as_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def _as_list(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return []
    return value


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


def _as_float_opt(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_bool_opt(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


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
class SkillModelTarget:
    provider: str
    mode: str
    model: str
    temperature: Optional[float]
    max_tokens: Optional[int]


@dataclass(frozen=True)
class SkillModelMatch:
    roles: List[str]
    kinds: List[str]
    needs_tools: Optional[bool]
    needs_json: Optional[bool]


@dataclass(frozen=True)
class SkillModelRoute:
    route_id: str
    priority: int
    match: SkillModelMatch
    target: SkillModelTarget


@dataclass(frozen=True)
class SkillModelPolicy:
    enabled: bool
    default: Optional[SkillModelTarget]
    routes: List[SkillModelRoute]


@dataclass(frozen=True)
class SkillAgentSpec:
    prompt_modules: List[str]
    context_providers: List[str]
    tools: SkillToolsPolicy
    budgets: SkillBudgets
    model_policy: SkillModelPolicy


@dataclass(frozen=True)
class SkillUiSpec:
    prompts: List[str]
    examples: List[str]


@dataclass(frozen=True)
class SkillRoutingSpec:
    keywords: List[str]
    negative_keywords: List[str]
    intents: List[str]
    keyword_weights: Dict[str, int]
    min_score: int
    min_margin: int
    confidence_floor: float
    match_mode: str


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    schema_version: int
    title: str
    desc: str
    allowed_roles: List[str]
    ui: SkillUiSpec
    routing: SkillRoutingSpec
    agent: SkillAgentSpec
    source_path: str
    instructions: str = ""
    source_type: str = "system"

    def as_public_dict(self) -> Dict[str, Any]:
        default_target = None
        if self.agent.model_policy.default is not None:
            default_target = {
                "provider": self.agent.model_policy.default.provider,
                "mode": self.agent.model_policy.default.mode,
                "model": self.agent.model_policy.default.model,
                "temperature": self.agent.model_policy.default.temperature,
                "max_tokens": self.agent.model_policy.default.max_tokens,
            }
        routes = []
        for route in self.agent.model_policy.routes:
            routes.append(
                {
                    "id": route.route_id,
                    "priority": route.priority,
                    "match": {
                        "roles": route.match.roles,
                        "kinds": route.match.kinds,
                        "needs_tools": route.match.needs_tools,
                        "needs_json": route.match.needs_json,
                    },
                    "target": {
                        "provider": route.target.provider,
                        "mode": route.target.mode,
                        "model": route.target.model,
                        "temperature": route.target.temperature,
                        "max_tokens": route.target.max_tokens,
                    },
                }
            )
        d: Dict[str, Any] = {
            "id": self.skill_id,
            "schema_version": self.schema_version,
            "title": self.title,
            "desc": self.desc,
            "allowed_roles": self.allowed_roles,
            "source_type": self.source_type,
            "prompts": self.ui.prompts,
            "examples": self.ui.examples,
            "routing": {
                "keywords": self.routing.keywords,
                "negative_keywords": self.routing.negative_keywords,
                "intents": self.routing.intents,
                "keyword_weights": dict(self.routing.keyword_weights),
                "min_score": int(self.routing.min_score),
                "min_margin": int(self.routing.min_margin),
                "confidence_floor": float(self.routing.confidence_floor),
                "match_mode": self.routing.match_mode,
            },
            "agent": {
                "prompt_modules": self.agent.prompt_modules,
                "context_providers": self.agent.context_providers,
                "tools": {"allow": self.agent.tools.allow, "deny": self.agent.tools.deny},
                "budgets": {
                    "max_tool_rounds": self.agent.budgets.max_tool_rounds,
                    "max_tool_calls": self.agent.budgets.max_tool_calls,
                },
                "model_policy": {
                    "enabled": self.agent.model_policy.enabled,
                    "default": default_target,
                    "routes": routes,
                },
            },
        }
        if self.instructions:
            d["instructions"] = self.instructions
        return d


def _parse_model_target(raw: Any) -> Optional[SkillModelTarget]:
    if not isinstance(raw, dict):
        return None
    provider = str(raw.get("provider") or "").strip()
    mode = str(raw.get("mode") or "").strip()
    model = str(raw.get("model") or "").strip()
    if not provider or not mode or not model:
        return None
    return SkillModelTarget(
        provider=provider,
        mode=mode,
        model=model,
        temperature=_as_float_opt(raw.get("temperature")),
        max_tokens=_as_int_opt(raw.get("max_tokens")),
    )


def _parse_model_policy(raw: Any) -> SkillModelPolicy:
    policy_raw = _as_dict(raw)
    default_target = _parse_model_target(policy_raw.get("default"))
    routes_raw = _as_list(policy_raw.get("routes"))
    routes: List[SkillModelRoute] = []
    for idx, item in enumerate(routes_raw):
        if not isinstance(item, dict):
            continue
        route_id = str(item.get("id") or "").strip() or f"route_{idx + 1}"
        priority = _as_int_opt(item.get("priority"))
        match_raw = _as_dict(item.get("match"))
        target = _parse_model_target(item.get("target"))
        if target is None:
            continue
        routes.append(
            SkillModelRoute(
                route_id=route_id,
                priority=max(0, int(priority if priority is not None else 100)),
                match=SkillModelMatch(
                    roles=_as_str_list(match_raw.get("roles")),
                    kinds=_as_str_list(match_raw.get("kinds")),
                    needs_tools=_as_bool_opt(match_raw.get("needs_tools")),
                    needs_json=_as_bool_opt(match_raw.get("needs_json")),
                ),
                target=target,
            )
        )
    routes.sort(key=lambda item: (-item.priority, item.route_id))
    has_any = bool(default_target) or bool(routes)
    enabled = _as_bool(policy_raw.get("enabled"), has_any)
    return SkillModelPolicy(enabled=enabled and has_any, default=default_target, routes=routes)


def _parse_routing(raw: Any) -> SkillRoutingSpec:
    routing_raw = _as_dict(raw)
    keywords = _as_str_list(routing_raw.get("keywords"))
    negative_keywords = _as_str_list(routing_raw.get("negative_keywords") or routing_raw.get("negativeKeywords"))
    intents = _as_str_list(routing_raw.get("intents"))

    keyword_weights_raw = _as_dict(routing_raw.get("keyword_weights"))
    keyword_weights: Dict[str, int] = {}
    for key, value in keyword_weights_raw.items():
        text = str(key or "").strip()
        if not text:
            continue
        weight = _as_int(value, 0)
        if weight <= 0:
            continue
        keyword_weights[text] = min(50, max(1, weight))

    min_score = max(1, _as_int(routing_raw.get("min_score"), 3))
    min_margin = max(0, _as_int(routing_raw.get("min_margin"), 1))
    confidence_floor = _as_float_opt(routing_raw.get("confidence_floor"))
    if confidence_floor is None:
        confidence_floor = 0.28
    confidence_floor = max(0.0, min(0.95, float(confidence_floor)))
    match_mode_raw = str(routing_raw.get("match_mode") or "").strip().lower()
    match_mode = match_mode_raw if match_mode_raw in {"substring", "word_boundary"} else "substring"

    return SkillRoutingSpec(
        keywords=keywords,
        negative_keywords=negative_keywords,
        intents=intents,
        keyword_weights=keyword_weights,
        min_score=min_score,
        min_margin=min_margin,
        confidence_floor=confidence_floor,
        match_mode=match_mode,
    )


def parse_skill_spec(skill_id: str, source_path: str, raw: Dict[str, Any]) -> SkillSpec:
    schema_version = _as_int_opt(raw.get("schema_version")) or _as_int_opt(raw.get("schemaVersion")) or 1

    title = str(raw.get("title") or raw.get("display_name") or raw.get("displayName") or "").strip() or "未命名技能"
    desc = str(raw.get("desc") or raw.get("description") or "").strip()
    allowed_roles = _as_str_list(raw.get("allowed_roles") or raw.get("allowedRoles"))

    ui_raw = _as_dict(raw.get("ui"))
    ui_prompts = _as_str_list(ui_raw.get("prompts") or raw.get("prompts"))
    ui_examples = _as_str_list(ui_raw.get("examples") or raw.get("examples"))
    ui = SkillUiSpec(prompts=ui_prompts, examples=ui_examples)
    routing = _parse_routing(raw.get("routing"))

    agent_raw = _as_dict(raw.get("agent"))
    prompt_modules = _as_str_list(agent_raw.get("prompt_modules") or agent_raw.get("promptModules"))
    context_providers = _as_str_list(agent_raw.get("context_providers") or agent_raw.get("contextProviders"))

    tools_raw = _as_dict(agent_raw.get("tools"))
    allow_value = tools_raw.get("allow")
    allow_list = _as_str_list(allow_value) if allow_value is not None else None
    deny_list = _as_str_list(tools_raw.get("deny"))
    tools = SkillToolsPolicy(allow=allow_list, deny=deny_list)

    budgets_raw = _as_dict(agent_raw.get("budgets"))
    budgets = SkillBudgets(
        max_tool_rounds=_as_int_opt(budgets_raw.get("max_tool_rounds")),
        max_tool_calls=_as_int_opt(budgets_raw.get("max_tool_calls")),
    )
    model_policy = _parse_model_policy(agent_raw.get("model_policy"))

    agent = SkillAgentSpec(
        prompt_modules=prompt_modules,
        context_providers=context_providers,
        tools=tools,
        budgets=budgets,
        model_policy=model_policy,
    )

    return SkillSpec(
        skill_id=skill_id,
        schema_version=int(schema_version),
        title=title,
        desc=desc,
        allowed_roles=allowed_roles,
        ui=ui,
        routing=routing,
        agent=agent,
        source_path=source_path,
        instructions=str(raw.get("instructions") or "").strip(),
        source_type=str(raw.get("source_type") or "system").strip(),
    )
