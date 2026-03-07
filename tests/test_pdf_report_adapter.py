from __future__ import annotations

from services.api.report_adapters.pdf_report_adapter import adapt_pdf_report_summary


def test_pdf_report_adapter_extracts_summary_from_text_payload() -> None:
    artifact = adapt_pdf_report_summary(
        {
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'report_id': 'pdf_report_1',
            'title': 'PDF 摘要报告',
            'text': '''
                班级报告
                摘要：班级整体在实验设计题上失分较多。
                主题：实验设计
                风险：受力分析概念混淆
                建议：先做概念辨析，再做分层练习。
            ''',
            'parse_confidence': 0.67,
        },
        {'source_uri': 'file:///tmp/class-report.pdf'},
    )

    assert artifact.artifact_type == 'class_signal_bundle'
    assert artifact.confidence == 0.67
    assert artifact.payload['theme_like_signals'][0]['theme'] == '实验设计'
    assert artifact.payload['risk_like_signals'][0]['risk'] == '受力分析概念混淆'
    assert artifact.evidence_refs[0].uri == 'file:///tmp/class-report.pdf'
