from __future__ import annotations

from services.api.survey_bundle_merge_service import merge_survey_evidence_bundles
from services.api.survey_bundle_models import SurveyAudienceScope, SurveyEvidenceBundle, SurveyMeta
from services.api.survey_report_parse_service import (
    SurveyReportParseDeps,
    parse_survey_report_payload,
)
from services.api.upload_text_service import extract_text_from_html


def _parse_deps() -> SurveyReportParseDeps:
    return SurveyReportParseDeps(
        extract_text_from_file=lambda path, **kwargs: "",
        extract_text_from_html=extract_text_from_html,
    )



def test_parse_survey_report_payload_applies_low_confidence_floor_for_empty_partial_inputs() -> None:
    payload = {
        "attachments": [
            {
                "name": "empty-report.pdf",
                "kind": "pdf",
            }
        ]
    }

    bundle = parse_survey_report_payload(provider="provider", payload=payload, deps=_parse_deps())

    assert bundle.attachments[0]["name"] == "empty-report.pdf"
    assert "title" in bundle.missing_fields
    assert "teacher_id" in bundle.missing_fields
    assert "class_name" in bundle.missing_fields
    assert "sample_size" in bundle.missing_fields
    assert "question_summaries" in bundle.missing_fields
    assert "attachment_text:empty-report.pdf" in bundle.missing_fields
    assert bundle.parse_confidence == 0.2



def test_merge_survey_evidence_bundles_keeps_lower_confidence_after_fill_in() -> None:
    structured_bundle = SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title="课堂反馈", provider="provider", submission_id="sub-1"),
        audience_scope=SurveyAudienceScope(teacher_id="teacher_1", class_name=None, sample_size=42),
        parse_confidence=0.98,
        missing_fields=["class_name"],
        provenance={"source": "structured"},
    )
    parsed_bundle = SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title=None, provider="provider", submission_id="sub-1"),
        audience_scope=SurveyAudienceScope(teacher_id=None, class_name="高二2403班", sample_size=42),
        parse_confidence=0.35,
        missing_fields=["teacher_id"],
        provenance={"source": "unstructured"},
    )

    merged = merge_survey_evidence_bundles(structured_bundle=structured_bundle, parsed_bundle=parsed_bundle)

    assert merged.audience_scope.class_name == "高二2403班"
    assert merged.parse_confidence == 0.35
    assert merged.missing_fields == ["class_name", "teacher_id"]
