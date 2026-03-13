from __future__ import annotations

import json

from services.api.specialist_agents.contracts import ArtifactRef, HandoffContract
from services.api.specialist_agents.survey_analyst import SurveyAnalystDeps, run_survey_analyst
from services.api.survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyGroupBreakdown,
    SurveyMeta,
    SurveyQuestionSummary,
)


def _bundle() -> SurveyEvidenceBundle:
    return SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title="课堂反馈问卷", provider="provider", submission_id="sub-1"),
        audience_scope=SurveyAudienceScope(teacher_id="teacher_1", class_name="高二2403班", sample_size=35),
        question_summaries=[
            SurveyQuestionSummary(
                question_id="Q1",
                prompt="本节课难度如何？",
                response_type="single_choice",
                stats={"偏难": 12, "适中": 20, "偏易": 3},
            )
        ],
        group_breakdowns=[
            SurveyGroupBreakdown(group_name="实验班", sample_size=20, stats={"Q1:偏难": 10})
        ],
        free_text_signals=[
            SurveyFreeTextSignal(theme="实验设计", evidence_count=6, excerpts=["推导太快了"])
        ],
        parse_confidence=0.78,
        missing_fields=["student_level_raw_data"],
        provenance={"source": "merged"},
    )



def test_survey_analyst_agent_sanitizes_llm_output_and_keeps_evidence_refs() -> None:
    handoff = HandoffContract(
        handoff_id="handoff_1",
        from_agent="coordinator",
        to_agent="survey_analyst",
        task_kind="survey.analysis",
        artifact_refs=[ArtifactRef(artifact_id="bundle_1", artifact_type="survey_evidence_bundle")],
        goal="输出班级洞察和教学建议",
        constraints={},
        budget={"max_tokens": 1600},
        return_schema={"type": "analysis_artifact"},
        status="prepared",
    )
    content = json.dumps(
        {
            "executive_summary": "班级整体在实验设计题上失分较多。",
            "key_signals": [
                {
                    "title": "实验设计理解偏弱",
                    "detail": "Q1 中选择偏难的比例较高。",
                    "evidence_refs": ["question:Q1", "theme:实验设计"],
                }
            ],
            "group_differences": [{"group_name": "实验班", "summary": "偏难反馈占比更高。"}],
            "teaching_recommendations": ["下节课增加实验设计拆解练习。"],
            "confidence_and_gaps": {"confidence": 0.81, "gaps": ["student_level_raw_data"]},
            "student_list": ["张三"],
            "action_plan": ["布置分层作业"],
        },
        ensure_ascii=False,
    )
    deps = SurveyAnalystDeps(
        call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": content}}]},
        prompt_loader=lambda: "survey analyst prompt",
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = run_survey_analyst(
        handoff=handoff,
        survey_evidence_bundle=_bundle(),
        teacher_context={"subject": "physics"},
        task_goal="输出班级洞察和教学建议",
        deps=deps,
    )

    assert result.agent_id == "survey_analyst"
    assert result.output["executive_summary"].startswith("班级整体")
    assert result.output["key_signals"][0]["evidence_refs"] == ["question:Q1", "theme:实验设计"]
    assert "student_list" not in result.output
    assert "action_plan" not in result.output



def test_survey_analyst_agent_falls_back_to_bundle_heuristics_on_invalid_llm_output() -> None:
    handoff = HandoffContract(
        handoff_id="handoff_2",
        from_agent="coordinator",
        to_agent="survey_analyst",
        task_kind="survey.analysis",
        artifact_refs=[ArtifactRef(artifact_id="bundle_1", artifact_type="survey_evidence_bundle")],
        goal="输出班级洞察和教学建议",
        constraints={},
        budget={"max_tokens": 1600},
        return_schema={"type": "analysis_artifact"},
        status="prepared",
    )
    deps = SurveyAnalystDeps(
        call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": "not-json"}}]},
        prompt_loader=lambda: "survey analyst prompt",
        diag_log=lambda *_args, **_kwargs: None,
    )

    result = run_survey_analyst(
        handoff=handoff,
        survey_evidence_bundle=_bundle(),
        teacher_context={"subject": "physics"},
        task_goal="输出班级洞察和教学建议",
        deps=deps,
    )

    assert result.output["executive_summary"]
    assert result.output["key_signals"]
    assert result.output["teaching_recommendations"]
    assert result.output["confidence_and_gaps"]["confidence"] == 0.78
