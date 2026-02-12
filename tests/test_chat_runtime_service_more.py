from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List

from services.api.chat_runtime_service import ChatRuntimeDeps, call_llm_runtime


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def as_chat_completion(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _FakeGateway:
    def __init__(self, plan: List[Any]):
        self.registry = {"default": {}}
        self.calls: List[Dict[str, Any]] = []
        self._plan = list(plan)

    def generate(self, req, provider=None, mode=None, model=None, allow_fallback=True, target_override=None):
        self.calls.append(
            {
                "provider": provider,
                "mode": mode,
                "model": model,
                "allow_fallback": allow_fallback,
                "target_override": isinstance(target_override, dict),
                "messages_len": len(req.messages or []),
            }
        )
        action = self._plan.pop(0)
        if isinstance(action, Exception):
            raise action
        return _FakeResponse(str(action))


class _SkillRuntime:
    def __init__(self, resolver):
        self.resolve_model_targets = resolver


def _install_routing_module(monkeypatch, *, errors, warnings, decision) -> None:
    mod = ModuleType("services.api.llm_routing")

    class RoutingContext:  # pragma: no cover - tiny container
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    mod.RoutingContext = RoutingContext  # type: ignore[attr-defined]
    mod.get_compiled_routing = lambda path, registry: SimpleNamespace(errors=list(errors), warnings=list(warnings))  # type: ignore[attr-defined]
    mod.resolve_routing = lambda compiled, ctx: decision  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "services.api.llm_routing", mod)


def _deps(
    gateway: _FakeGateway,
    logs: List[Any],
    limiter_seen: List[Any],
    *,
    resolve_teacher_model_registry,
    resolve_teacher_provider_target,
):
    default_limiter = object()
    student_limiter = object()
    teacher_limiter = object()

    @contextmanager
    def _limit(limiter):
        limiter_seen.append(limiter)
        yield

    deps = ChatRuntimeDeps(
        gateway=gateway,
        limit=_limit,
        default_limiter=default_limiter,
        student_limiter=student_limiter,
        teacher_limiter=teacher_limiter,
        resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher_default"),
        resolve_teacher_model_registry=resolve_teacher_model_registry,
        resolve_teacher_provider_target=resolve_teacher_provider_target,
        ensure_teacher_routing_file=lambda actor: Path(f"/tmp/{actor}.json"),
        routing_config_path_for_role=lambda role_hint, teacher_id: Path("/tmp/default-routing.json"),
        diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        monotonic=lambda: 100.0 + len(logs),
    )
    return deps, default_limiter, student_limiter, teacher_limiter


def test_runtime_uses_default_limiter_and_gateway_fallback(monkeypatch) -> None:
    decision = SimpleNamespace(reason="", matched_rule_id=None, selected=False, candidates=[])
    _install_routing_module(monkeypatch, errors=["err-a"], warnings=["warn-a"], decision=decision)

    logs: List[Any] = []
    limiter_seen: List[Any] = []
    gateway = _FakeGateway(["fallback-ok"])
    deps, default_limiter, _, _ = _deps(
        gateway,
        logs,
        limiter_seen,
        resolve_teacher_model_registry=lambda _actor: {},
        resolve_teacher_provider_target=lambda *_args: None,
    )

    out = call_llm_runtime([{"role": "user", "content": "hello"}], deps=deps)

    assert out["choices"][0]["message"]["content"] == "fallback-ok"
    assert limiter_seen[-1] is default_limiter
    assert gateway.calls[0]["allow_fallback"] is True
    payload = logs[-1][1]
    assert payload["route_reason"] == "gateway_fallback"
    assert payload["route_validation_errors"] == ["err-a"]
    assert payload["route_validation_warnings"] == ["warn-a"]


def test_runtime_teacher_selected_target_override_and_registry_error(monkeypatch) -> None:
    candidate = SimpleNamespace(
        channel_id="c-1",
        provider="p-1",
        mode="m-1",
        model="model-1",
        temperature=0.2,
        max_tokens=321,
    )
    decision = SimpleNamespace(reason="matched", matched_rule_id="rule-1", selected=True, candidates=[candidate])
    _install_routing_module(monkeypatch, errors=[], warnings=[], decision=decision)

    logs: List[Any] = []
    limiter_seen: List[Any] = []
    gateway = _FakeGateway(["route-ok"])
    deps, _, _, teacher_limiter = _deps(
        gateway,
        logs,
        limiter_seen,
        resolve_teacher_model_registry=lambda _actor: (_ for _ in ()).throw(RuntimeError("registry boom")),
        resolve_teacher_provider_target=lambda *_args: {"provider": "forced"},
    )

    out = call_llm_runtime(
        [{"role": "user", "content": "hello"}],
        deps=deps,
        role_hint="teacher",
        teacher_id="teacher-a",
    )

    assert out["choices"][0]["message"]["content"] == "route-ok"
    assert limiter_seen[-1] is teacher_limiter
    assert gateway.calls[0]["target_override"] is True
    assert gateway.calls[0]["allow_fallback"] is False
    payload = logs[-1][1]
    assert payload["route_selected"] is True
    assert payload["route_source"] == "teacher_routing"
    assert "registry boom" in payload["route_exception"]


def test_runtime_teacher_routing_attempt_errors_then_success(monkeypatch) -> None:
    candidate_1 = SimpleNamespace(channel_id="c-1", provider="p1", mode="m1", model="a", temperature=None, max_tokens=None)
    candidate_2 = SimpleNamespace(channel_id="c-2", provider="p2", mode="m2", model="b", temperature=None, max_tokens=None)
    decision = SimpleNamespace(reason="matched", matched_rule_id="rule-x", selected=True, candidates=[candidate_1, candidate_2])
    _install_routing_module(monkeypatch, errors=[], warnings=[], decision=decision)

    logs: List[Any] = []
    limiter_seen: List[Any] = []
    gateway = _FakeGateway([RuntimeError("route fail"), "route-ok"])

    def _provider_target(_actor, provider, mode, model):
        if provider == "p1":
            raise RuntimeError("target fail")
        return None

    deps, _, _, _ = _deps(
        gateway,
        logs,
        limiter_seen,
        resolve_teacher_model_registry=lambda _actor: {},
        resolve_teacher_provider_target=_provider_target,
    )

    out = call_llm_runtime(
        [{"role": "user", "content": "hello"}],
        deps=deps,
        role_hint="teacher",
        teacher_id="teacher-a",
    )

    assert out["choices"][0]["message"]["content"] == "route-ok"
    payload = logs[-1][1]
    assert payload["route_channel_id"] == "c-2"
    sources = [item.get("source") for item in payload["route_attempt_errors"]]
    assert "teacher_provider_target" in sources
    assert "teacher_routing" in sources


def test_runtime_skill_policy_attempt_error_then_success(monkeypatch) -> None:
    decision = SimpleNamespace(reason="no_route", matched_rule_id=None, selected=False, candidates=[])
    _install_routing_module(monkeypatch, errors=[], warnings=[], decision=decision)

    logs: List[Any] = []
    limiter_seen: List[Any] = []
    gateway = _FakeGateway([RuntimeError("policy fail"), "policy-ok"])

    def _resolver(**kwargs):
        return [
            {"provider": "", "mode": "x", "model": "y"},
            {"provider": "p1", "mode": "m1", "model": "a", "route_id": "r1"},
            {"provider": "p2", "mode": "m2", "model": "b", "route_id": "default"},
        ]

    def _provider_target(_actor, provider, mode, model):
        if provider == "p1":
            raise RuntimeError("policy target fail")
        return None

    deps, _, _, _ = _deps(
        gateway,
        logs,
        limiter_seen,
        resolve_teacher_model_registry=lambda _actor: {},
        resolve_teacher_provider_target=_provider_target,
    )

    out = call_llm_runtime(
        [{"role": "user", "content": "hello"}],
        deps=deps,
        role_hint="teacher",
        teacher_id="teacher-a",
        skill_runtime=_SkillRuntime(_resolver),
    )

    assert out["choices"][0]["message"]["content"] == "policy-ok"
    payload = logs[-1][1]
    assert payload["route_source"] == "skill_policy"
    assert payload["route_policy_route_id"] == "default"
    assert payload["route_reason"] == "skill_policy_default"
    sources = [item.get("source") for item in payload["route_attempt_errors"]]
    assert "skill_policy_provider_target" in sources
    assert "skill_policy" in sources


def test_runtime_skill_policy_resolver_exception_fallback(monkeypatch) -> None:
    decision = SimpleNamespace(reason="", matched_rule_id=None, selected=False, candidates=[])
    _install_routing_module(monkeypatch, errors=[], warnings=[], decision=decision)

    logs: List[Any] = []
    limiter_seen: List[Any] = []
    gateway = _FakeGateway(["fallback-ok"])

    deps, _, _, _ = _deps(
        gateway,
        logs,
        limiter_seen,
        resolve_teacher_model_registry=lambda _actor: {},
        resolve_teacher_provider_target=lambda *_args: None,
    )

    out = call_llm_runtime(
        [{"role": "user", "content": "hello"}],
        deps=deps,
        role_hint="teacher",
        teacher_id="teacher-a",
        skill_runtime=_SkillRuntime(lambda **kwargs: (_ for _ in ()).throw(RuntimeError("resolver boom"))),
    )

    assert out["choices"][0]["message"]["content"] == "fallback-ok"
    assert gateway.calls[0]["allow_fallback"] is True
    payload = logs[-1][1]
    assert payload["route_reason"] == "gateway_fallback"
    assert "resolver boom" in payload["route_policy_exception"]


def test_runtime_skill_policy_target_override_dict_path(monkeypatch) -> None:
    decision = SimpleNamespace(reason="no_route", matched_rule_id=None, selected=False, candidates=[])
    _install_routing_module(monkeypatch, errors=[], warnings=[], decision=decision)

    logs: List[Any] = []
    limiter_seen: List[Any] = []
    gateway = _FakeGateway(["policy-override-ok"])

    deps, _, _, _ = _deps(
        gateway,
        logs,
        limiter_seen,
        resolve_teacher_model_registry=lambda _actor: {},
        resolve_teacher_provider_target=lambda *_args: {"provider": "override"},
    )

    out = call_llm_runtime(
        [{"role": "user", "content": "hello"}],
        deps=deps,
        role_hint="teacher",
        teacher_id="teacher-a",
        skill_runtime=_SkillRuntime(
            lambda **kwargs: [
                {"provider": "", "mode": "", "model": ""},  # invalid, should continue
                {"provider": "p2", "mode": "m2", "model": "b", "route_id": "default"},
            ]
        ),
    )

    assert out["choices"][0]["message"]["content"] == "policy-override-ok"
    assert gateway.calls[0]["target_override"] is True
    assert gateway.calls[0]["allow_fallback"] is False
    payload = logs[-1][1]
    assert payload["route_source"] == "skill_policy"
