from __future__ import annotations

from typing import Any, Callable


BindingFactory = Callable[..., Any]



def runtime_deps_factory_lookup() -> dict[str, BindingFactory]:
    from .runtime_builder import (
        build_class_signal_analyst_deps,
        build_survey_analyst_deps,
        build_video_homework_analyst_deps,
    )

    return {
        'build_survey_analyst_deps': build_survey_analyst_deps,
        'build_class_signal_analyst_deps': build_class_signal_analyst_deps,
        'build_video_homework_analyst_deps': build_video_homework_analyst_deps,
    }



def runtime_runner_lookup() -> dict[str, BindingFactory]:
    from ..specialist_agents.class_signal_analyst import run_class_signal_analyst
    from ..specialist_agents.survey_analyst import run_survey_analyst
    from ..specialist_agents.video_homework_analyst import run_video_homework_analyst

    return {
        'survey_analyst': run_survey_analyst,
        'class_signal_analyst': run_class_signal_analyst,
        'video_homework_analyst': run_video_homework_analyst,
    }



def report_provider_factory_lookup() -> dict[str, BindingFactory]:
    from ..analysis_report_service import (
        build_class_report_analysis_report_provider,
        build_survey_analysis_report_provider,
        build_video_homework_analysis_report_provider,
    )

    return {
        'build_class_report_analysis_report_provider': build_class_report_analysis_report_provider,
        'build_survey_analysis_report_provider': build_survey_analysis_report_provider,
        'build_video_homework_analysis_report_provider': build_video_homework_analysis_report_provider,
    }
