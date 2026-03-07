from __future__ import annotations

from services.api.artifacts.registry import build_platform_artifact_registry
from services.api.report_adapters.self_hosted_form_adapter import adapt_self_hosted_form_json


def test_self_hosted_form_adapter_normalizes_json_payload_to_class_signal_bundle() -> None:
    artifact = adapt_self_hosted_form_json(
        {
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'sample_size': 36,
            'report_id': 'class_report_1',
            'title': '课堂反馈周报',
            'questions': [
                {
                    'id': 'Q1',
                    'prompt': '课堂难点',
                    'summary': '实验设计题仍是主要难点。',
                    'stats': {'实验设计': 15, '计算': 8},
                }
            ],
            'themes': [
                {'theme': '实验设计', 'summary': '变量控制仍是高频问题。', 'evidence_count': 6, 'excerpts': ['变量控制不清']}
            ],
            'risks': [
                {'risk': '受力分析概念混淆', 'severity': 'medium', 'summary': '平衡态与受力图判断混淆'}
            ],
            'summary': '班级整体在实验设计题上失分较多。',
        },
        {'source_uri': 'file:///tmp/class-report.json'},
    )

    assert artifact.artifact_type == 'class_signal_bundle'
    assert artifact.subject_scope['teacher_id'] == 'teacher_1'
    assert artifact.payload['question_like_signals'][0]['title'] == '课堂难点'
    assert artifact.payload['theme_like_signals'][0]['theme'] == '实验设计'
    assert artifact.payload['risk_like_signals'][0]['risk'] == '受力分析概念混淆'
    assert artifact.provenance['adapter_id'] == 'class_report.self_hosted_form.adapter'

    registry = build_platform_artifact_registry()
    assert registry.get('class_report.self_hosted_form.adapter').output_artifact_type == 'class_signal_bundle'
