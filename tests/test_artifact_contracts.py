from __future__ import annotations

from services.api.artifacts.contracts import ArtifactEnvelope
from services.api.survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyMeta,
    SurveyQuestionSummary,
)


def test_artifact_envelope_roundtrip() -> None:
    artifact = ArtifactEnvelope(
        artifact_type='survey_evidence_bundle',
        schema_version='v1',
        subject_scope={'teacher_id': 'teacher_1', 'class_name': '高二2403班'},
        evidence_refs=[
            {
                'ref_id': 'report.pdf',
                'kind': 'attachment',
                'uri': 'survey://job_1/report.pdf',
                'mime_type': 'application/pdf',
            }
        ],
        confidence=0.83,
        missing_fields=['teacher_name'],
        provenance={'source': 'structured', 'provider': 'provider'},
        payload={'survey_meta': {'title': '课堂反馈问卷'}},
    )

    payload = artifact.model_dump()

    assert payload['artifact_type'] == 'survey_evidence_bundle'
    assert payload['subject_scope']['teacher_id'] == 'teacher_1'
    assert payload['evidence_refs'][0]['ref_id'] == 'report.pdf'
    assert payload['confidence'] == 0.83



def test_survey_bundle_exports_generic_artifact_envelope() -> None:
    bundle = SurveyEvidenceBundle(
        survey_meta=SurveyMeta(title='课堂反馈问卷', provider='provider', submission_id='sub-1'),
        audience_scope=SurveyAudienceScope(teacher_id='teacher_1', class_name='高二2403班', sample_size=35),
        question_summaries=[
            SurveyQuestionSummary(
                question_id='Q1',
                prompt='本节课难度如何？',
                response_type='single_choice',
                stats={'偏难': 12, '适中': 20, '偏易': 3},
            )
        ],
        free_text_signals=[
            SurveyFreeTextSignal(theme='实验设计', evidence_count=5, excerpts=['推导太快了'])
        ],
        attachments=[
            {
                'name': 'report.pdf',
                'kind': 'attachment',
                'uri': 'survey://job_1/report.pdf',
                'mime_type': 'application/pdf',
            }
        ],
        parse_confidence=0.62,
        missing_fields=['teacher_name'],
        provenance={'source': 'structured', 'provider': 'provider'},
    )

    artifact = bundle.to_artifact_envelope()

    assert artifact.artifact_type == 'survey_evidence_bundle'
    assert artifact.schema_version == 'v1'
    assert artifact.subject_scope['teacher_id'] == 'teacher_1'
    assert artifact.subject_scope['class_name'] == '高二2403班'
    assert artifact.confidence == 0.62
    assert artifact.evidence_refs[0].ref_id == 'report.pdf'
    assert artifact.payload['survey_meta']['title'] == '课堂反馈问卷'
