from __future__ import annotations

from services.api.survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyGroupBreakdown,
    SurveyMeta,
    SurveyQuestionSummary,
)



def test_survey_evidence_bundle_model_roundtrip() -> None:
    bundle = SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title="课堂反馈", provider="provider", submission_id="sub-1"),
        audience_scope=SurveyAudienceScope(teacher_id="teacher_1", class_name="高二2403班", sample_size=42),
        question_summaries=[
            SurveyQuestionSummary(
                question_id="Q1",
                prompt="这节课你最困惑的点是什么？",
                response_type="single_choice",
                stats={"A": 12, "B": 30},
            )
        ],
        group_breakdowns=[
            SurveyGroupBreakdown(group_name="物理提高组", sample_size=18, stats={"Q1:A": 8})
        ],
        free_text_signals=[
            SurveyFreeTextSignal(theme="实验设计", evidence_count=6, excerpts=["不会控制变量"])
        ],
        attachments=[{"name": "report.pdf"}],
        parse_confidence=0.92,
        missing_fields=["deadline"],
        provenance={"source": "structured", "provider": "provider"},
    )

    payload = bundle.model_dump()
    assert payload["survey_meta"]["title"] == "课堂反馈"
    assert payload["audience_scope"]["sample_size"] == 42
    assert payload["question_summaries"][0]["question_id"] == "Q1"
    assert payload["parse_confidence"] == 0.92
