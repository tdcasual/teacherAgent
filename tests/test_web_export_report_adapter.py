from __future__ import annotations

from services.api.report_adapters.web_export_report_adapter import adapt_web_export_html


def test_web_export_report_adapter_extracts_theme_and_risk_signals_from_html() -> None:
    artifact = adapt_web_export_html(
        {
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'report_id': 'web_report_1',
            'title': '网页导出报告',
            'html': '''
                <html>
                  <body>
                    <h1>高二2403班课堂反馈</h1>
                    <p>摘要：班级整体在实验设计题上失分较多。</p>
                    <p>主题：实验设计</p>
                    <p>风险：受力分析概念混淆</p>
                    <p>建议：先复盘变量控制，再做即时检测。</p>
                  </body>
                </html>
            ''',
        },
        {'source_uri': 'https://reports.example.com/class-report-1'},
    )

    assert artifact.artifact_type == 'class_signal_bundle'
    assert artifact.payload['theme_like_signals'][0]['theme'] == '实验设计'
    assert artifact.payload['risk_like_signals'][0]['risk'] == '受力分析概念混淆'
    assert '班级整体在实验设计题上失分较多。' in artifact.payload['narrative_blocks'][0]
    assert artifact.provenance['source_uri'] == 'https://reports.example.com/class-report-1'
