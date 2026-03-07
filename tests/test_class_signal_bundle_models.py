from __future__ import annotations

from services.api.class_signal_bundle_models import (
    ClassSignalBundle,
    ClassSignalQuestionLike,
    ClassSignalRiskLike,
    ClassSignalScope,
    ClassSignalSourceMeta,
    ClassSignalThemeLike,
)


def test_class_signal_bundle_exports_generic_artifact_envelope() -> None:
    bundle = ClassSignalBundle(
        source_meta=ClassSignalSourceMeta(
            title='课堂反馈周报',
            provider='self_hosted_form',
            source_type='self_hosted_form_json',
            report_id='class_report_1',
        ),
        class_scope=ClassSignalScope(
            teacher_id='teacher_1',
            class_name='高二2403班',
            sample_size=36,
        ),
        question_like_signals=[
            ClassSignalQuestionLike(
                signal_id='question_1',
                title='课堂难点',
                summary='实验设计题仍是主要难点。',
                stats={'实验设计': 15, '计算': 8},
                evidence_refs=['question:1'],
            )
        ],
        theme_like_signals=[
            ClassSignalThemeLike(
                theme='实验设计',
                summary='多个来源都提到变量控制与步骤拆解问题。',
                evidence_count=6,
                excerpts=['变量控制不清'],
                evidence_refs=['theme:实验设计'],
            )
        ],
        risk_like_signals=[
            ClassSignalRiskLike(
                risk='受力分析概念混淆',
                severity='medium',
                summary='部分学生把平衡态和受力图判定混在一起。',
                evidence_refs=['risk:受力分析概念混淆'],
            )
        ],
        narrative_blocks=['班级整体在实验设计题上失分较多。'],
        attachments=[
            {
                'name': 'weekly-report.pdf',
                'kind': 'attachment',
                'uri': 'class-report://bundle_1/weekly-report.pdf',
                'mime_type': 'application/pdf',
            }
        ],
        parse_confidence=0.76,
        missing_fields=['student_level_raw_data'],
        provenance={'source': 'adapter', 'provider': 'self_hosted_form'},
    )

    artifact = bundle.to_artifact_envelope()

    assert artifact.artifact_type == 'class_signal_bundle'
    assert artifact.subject_scope['teacher_id'] == 'teacher_1'
    assert artifact.subject_scope['class_name'] == '高二2403班'
    assert artifact.confidence == 0.76
    assert artifact.evidence_refs[0].ref_id == 'weekly-report.pdf'
    assert artifact.payload['theme_like_signals'][0]['theme'] == '实验设计'
