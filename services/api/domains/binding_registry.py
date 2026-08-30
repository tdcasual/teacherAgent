from __future__ import annotations

from typing import Any, Callable

from ..specialist_agents.reviewer_analyst import run_reviewer_analyst
from ..specialist_agents.video_homework_analyst import (
    VideoHomeworkAnalystDeps,
    load_video_homework_analyst_prompt,
    run_video_homework_analyst,
)

BindingFactory = Callable[..., Any]


def build_video_homework_analyst_deps(core: Any) -> VideoHomeworkAnalystDeps:
    return VideoHomeworkAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_video_homework_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )


_RUNTIME_DEPS_FACTORIES: tuple[BindingFactory, ...] = (
    build_video_homework_analyst_deps,
)

_RUNTIME_RUNNERS: dict[str, BindingFactory] = {
    'video_homework_analyst': run_video_homework_analyst,
    'reviewer_analyst': run_reviewer_analyst,
}


def runtime_deps_factory_lookup() -> dict[str, BindingFactory]:
    return {factory.__name__: factory for factory in _RUNTIME_DEPS_FACTORIES}


def runtime_runner_lookup() -> dict[str, BindingFactory]:
    return dict(_RUNTIME_RUNNERS)


def report_provider_factory_lookup() -> dict[str, BindingFactory]:
    return {}
