from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core_runtime import CoreRuntime


@dataclass(frozen=True)
class AppContainer:
    core: CoreRuntime
    llm_gateway: Any
    observability: Any


def _default_llm_gateway(core: CoreRuntime) -> Any:
    gateway = getattr(core, "LLM_GATEWAY", None)
    if gateway is not None:
        return gateway
    from llm_gateway import LLMGateway

    return LLMGateway()


def _default_observability() -> Any:
    from .observability import ObservabilityStore

    return ObservabilityStore()


def build_app_container(
    *,
    core: CoreRuntime,
    llm_gateway: Any | None = None,
    observability: Any | None = None,
) -> AppContainer:
    return AppContainer(
        core=core,
        llm_gateway=_default_llm_gateway(core) if llm_gateway is None else llm_gateway,
        observability=_default_observability() if observability is None else observability,
    )


def resolve_observability(holder: Any) -> Any:
    """Read observability from app.state.container; fall back to the process store."""
    state = getattr(holder, "state", None)
    if state is None:
        state = holder
    container = getattr(state, "container", None)
    obs = getattr(container, "observability", None) if container is not None else None
    if obs is not None:
        return obs
    from .observability import OBSERVABILITY

    return OBSERVABILITY
