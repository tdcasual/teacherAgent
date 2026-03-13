from __future__ import annotations

from services.api.survey_bundle_merge_service import merge_survey_evidence_bundles
from services.api.survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyGroupBreakdown,
    SurveyMeta,
    SurveyQuestionSummary,
)


def test_merge_survey_evidence_bundles_combines_fields_provenance_and_confidence() -> None:
    structured_bundle = SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title="课堂反馈问卷", provider="provider", submission_id="sub-1"),
        audience_scope=SurveyAudienceScope(teacher_id="teacher_1", class_name=None, sample_size=35),
        question_summaries=[
            SurveyQuestionSummary(
                question_id="Q1",
                prompt="本节课难度如何？",
                response_type="single_choice",
                stats={"偏难": 12},
            )
        ],
        free_text_signals=[
            SurveyFreeTextSignal(theme="公式推导", evidence_count=4, excerpts=["推导太快了"])
        ],
        attachments=[{"name": "payload.json", "kind": "structured"}],
        parse_confidence=1.0,
        missing_fields=["class_name"],
        provenance={"source": "structured", "provider": "provider"},
    )
    parsed_bundle = SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title=None, provider="provider", submission_id="sub-1"),
        audience_scope=SurveyAudienceScope(teacher_id=None, class_name="高二2403班", sample_size=35),
        question_summaries=[
            SurveyQuestionSummary(
                question_id="Q1",
                prompt=None,
                response_type="single_choice",
                stats={"适中": 20, "偏易": 3},
            ),
            SurveyQuestionSummary(
                question_id="Q2",
                prompt="节奏是否合适？",
                response_type="single_choice",
                stats={"偏快": 8, "适中": 24, "偏慢": 3},
            ),
        ],
        group_breakdowns=[
            SurveyGroupBreakdown(group_name="实验班", sample_size=20, stats={"Q1:偏难": 10})
        ],
        free_text_signals=[
            SurveyFreeTextSignal(theme="公式推导", evidence_count=6, excerpts=["例题太少"])
        ],
        attachments=[{"name": "report.pdf", "kind": "pdf"}],
        parse_confidence=0.62,
        missing_fields=["teacher_id"],
        provenance={"source": "unstructured", "provider": "provider", "attachments": 1},
    )

    merged = merge_survey_evidence_bundles(structured_bundle=structured_bundle, parsed_bundle=parsed_bundle)

    assert merged.survey_meta.title == "课堂反馈问卷"
    assert merged.audience_scope.teacher_id == "teacher_1"
    assert merged.audience_scope.class_name == "高二2403班"
    assert {item.question_id for item in merged.question_summaries} == {"Q1", "Q2"}
    q1 = next(item for item in merged.question_summaries if item.question_id == "Q1")
    assert q1.stats == {"偏难": 12, "适中": 20, "偏易": 3}
    assert merged.group_breakdowns[0].group_name == "实验班"
    signal = merged.free_text_signals[0]
    assert signal.theme == "公式推导"
    assert signal.evidence_count == 6
    assert signal.excerpts == ["推导太快了", "例题太少"]
    assert len(merged.attachments) == 2
    assert merged.parse_confidence == 0.62
    assert merged.missing_fields == ["class_name", "teacher_id"]
    assert merged.provenance["source"] == "merged"
    assert len(merged.provenance["sources"]) == 2
