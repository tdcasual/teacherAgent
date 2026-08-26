from __future__ import annotations

from typing import Any, Callable

from ..specialist_agents.class_signal_analyst import (
    ClassSignalAnalystDeps,
    load_class_signal_analyst_prompt,
    run_class_signal_analyst,
)
from ..specialist_agents.reviewer_analyst import run_reviewer_analyst
from ..specialist_agents.survey_analyst import (
    SurveyAnalystDeps,
    load_survey_analyst_prompt,
    run_survey_analyst,
)
from ..specialist_agents.video_homework_analyst import (
    VideoHomeworkAnalystDeps,
    load_video_homework_analyst_prompt,
    run_video_homework_analyst,
)

BindingFactory = Callable[..., Any]


def build_survey_analyst_deps(core: Any) -> SurveyAnalystDeps:
    return SurveyAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_survey_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )


def build_class_signal_analyst_deps(core: Any) -> ClassSignalAnalystDeps:
    return ClassSignalAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_class_signal_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )


def build_video_homework_analyst_deps(core: Any) -> VideoHomeworkAnalystDeps:
    return VideoHomeworkAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_video_homework_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )


_RUNTIME_DEPS_FACTORIES: tuple[BindingFactory, ...] = (
    build_survey_analyst_deps,
    build_class_signal_analyst_deps,
    build_video_homework_analyst_deps,
)

_RUNTIME_RUNNERS: dict[str, BindingFactory] = {
    'survey_analyst': run_survey_analyst,
    'class_signal_analyst': run_class_signal_analyst,
    'video_homework_analyst': run_video_homework_analyst,
    'reviewer_analyst': run_reviewer_analyst,
}


def runtime_deps_factory_lookup() -> dict[str, BindingFactory]:
    return {factory.__name__: factory for factory in _RUNTIME_DEPS_FACTORIES}


def runtime_runner_lookup() -> dict[str, BindingFactory]:
    return dict(_RUNTIME_RUNNERS)


def report_provider_factory_lookup() -> dict[str, BindingFactory]:
    from ..analysis_report_service import (
        build_class_report_analysis_report_provider,
        build_survey_analysis_report_provider,
        build_video_homework_analysis_report_provider,
    )

    return {
        factory.__name__: factory
        for factory in (
            build_class_report_analysis_report_provider,
            build_survey_analysis_report_provider,
            build_video_homework_analysis_report_provider,
        )
    }
