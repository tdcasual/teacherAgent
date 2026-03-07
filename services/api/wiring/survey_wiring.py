from __future__ import annotations

from typing import Any, Optional

from ..specialist_agents.registry import SpecialistAgentRegistry, SpecialistAgentSpec
from ..specialist_agents.runtime import SpecialistAgentRuntime
from ..specialist_agents.survey_analyst import SurveyAnalystDeps, load_survey_analyst_prompt, run_survey_analyst
from ..survey.deps import SurveyApplicationDeps, build_survey_application_deps
from ..survey_report_service import (
    build_survey_report_deps,
    get_survey_report as _get_survey_report_impl,
    list_survey_reports as _list_survey_reports_impl,
    list_survey_review_queue as _list_survey_review_queue_impl,
    rerun_survey_report as _rerun_survey_report_impl,
)
from ..survey_repository import load_survey_bundle as _load_survey_bundle_impl
from . import get_app_core as _app_core



def build_survey_deps(core: Any) -> SurveyApplicationDeps:
    return build_survey_application_deps(core)



def build_survey_analyst_deps(core: Any) -> SurveyAnalystDeps:
    return SurveyAnalystDeps(
        call_llm=getattr(core, "call_llm", lambda *_args, **_kwargs: {}),
        prompt_loader=load_survey_analyst_prompt,
        diag_log=getattr(core, "diag_log", lambda *_args, **_kwargs: None),
    )



def build_survey_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    registry = SpecialistAgentRegistry()
    analyst_deps = build_survey_analyst_deps(core)

    def _runner(handoff):
        constraints = handoff.constraints if isinstance(handoff.constraints, dict) else {}
        return run_survey_analyst(
            handoff=handoff,
            survey_evidence_bundle=dict(constraints.get("survey_evidence_bundle") or {}),
            teacher_context=dict(constraints.get("teacher_context") or {}),
            task_goal=str(handoff.goal or "").strip(),
            deps=analyst_deps,
        )

    registry.register(
        SpecialistAgentSpec(
            agent_id="survey_analyst",
            display_name="Survey Analyst",
            roles=["teacher"],
            accepted_artifacts=["survey_evidence_bundle"],
            task_kinds=["survey.analysis"],
            direct_answer_capable=False,
            takeover_policy="coordinator_only",
            tool_allowlist=["llm.generate"],
            budgets={"default": {"max_tokens": 1600, "timeout_sec": 45, "max_steps": 2}},
            memory_policy="no_direct_memory_write",
            output_schema={"type": "analysis_artifact"},
            evaluation_suite=["survey_v1_golden"],
        ),
        runner=_runner,
    )
    return registry



def build_survey_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return SpecialistAgentRuntime(build_survey_specialist_registry(core))



def survey_list_reports(teacher_id: str, status: Optional[str] = None, *, core: Any | None = None):
    return _list_survey_reports_impl(
        teacher_id=teacher_id,
        status=status,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_get_report(report_id: str, teacher_id: str, *, core: Any | None = None):
    return _get_survey_report_impl(
        report_id=report_id,
        teacher_id=teacher_id,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_rerun_report(report_id: str, teacher_id: str, reason: Optional[str] = None, *, core: Any | None = None):
    return _rerun_survey_report_impl(
        report_id=report_id,
        teacher_id=teacher_id,
        reason=reason,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_list_review_queue(teacher_id: str, *, core: Any | None = None):
    return _list_survey_review_queue_impl(
        teacher_id=teacher_id,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_load_bundle(job_id: str, *, core: Any | None = None):
    return _load_survey_bundle_impl(job_id, core=_app_core(core))
