from __future__ import annotations

import json
from pathlib import Path

from services.api.class_report_orchestrator_service import build_class_report_orchestrator_deps, process_class_report_job
from services.api.class_report_service import (
    build_class_report_deps,
    list_class_report_review_queue,
    load_class_report,
    load_class_report_job,
    load_class_signal_bundle,
    write_class_report_job,
)


class _Core:
    def __init__(self, root: Path, call_llm) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'
        self.call_llm = call_llm
        self.diag_log = lambda *_args, **_kwargs: None



def test_process_class_report_job_runs_normal_flow_to_teacher_notified(tmp_path: Path) -> None:
    content = json.dumps(
        {
            'executive_summary': '班级整体在实验设计题上失分较多。',
            'key_signals': [
                {
                    'title': '实验设计理解偏弱',
                    'detail': '变量控制与实验目的判断错误较集中。',
                    'evidence_refs': ['question:Q1', 'theme:实验设计'],
                }
            ],
            'teaching_recommendations': ['下节课增加实验设计拆解练习。'],
            'confidence_and_gaps': {'confidence': 0.82, 'gaps': []},
        },
        ensure_ascii=False,
    )
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': content}}]})
    service_deps = build_class_report_deps(core)
    write_class_report_job(
        'job_1',
        {
            'job_id': 'job_1',
            'report_id': 'class_report_1',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'webhook_received',
            'created_at': '2026-03-07T10:00:00',
            'input_type': 'self_hosted_form_json',
            'raw_payload': {
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
                    {'theme': '实验设计', 'summary': '变量控制仍是高频问题。', 'evidence_count': 6}
                ],
                'risks': [
                    {'risk': '受力分析概念混淆', 'severity': 'medium', 'summary': '平衡态与受力图判断混淆'}
                ],
                'summary': '班级整体在实验设计题上失分较多。',
            },
        },
        deps=service_deps,
    )

    result = process_class_report_job('job_1', deps=build_class_report_orchestrator_deps(core))
    job = load_class_report_job('job_1', deps=service_deps)
    bundle = load_class_signal_bundle('job_1', deps=service_deps)
    report = load_class_report('class_report_1', deps=service_deps)

    assert result['status'] == 'teacher_notified'
    assert job['status'] == 'teacher_notified'
    assert job['strategy_id'] == 'class_signal.teacher.report'
    assert bundle['source_meta']['title'] == '课堂反馈周报'
    assert report['status'] == 'analysis_ready'
    assert report['analysis_artifact']['executive_summary'].startswith('班级整体')



def test_process_class_report_job_routes_low_confidence_bundle_to_review(tmp_path: Path) -> None:
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    service_deps = build_class_report_deps(core)
    write_class_report_job(
        'job_low',
        {
            'job_id': 'job_low',
            'report_id': 'class_report_low',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'webhook_received',
            'created_at': '2026-03-07T10:05:00',
            'input_type': 'pdf_report_summary',
            'raw_payload': {
                'teacher_id': 'teacher_1',
                'class_name': '高二2403班',
                'report_id': 'class_report_low',
                'title': 'PDF 摘要报告',
                'text': '摘要：班级整体在实验设计题上失分较多。\n主题：实验设计\n风险：受力分析概念混淆\n建议：先做概念辨析，再做分层练习。',
                'parse_confidence': 0.45,
            },
        },
        deps=service_deps,
    )

    result = process_class_report_job('job_low', deps=build_class_report_orchestrator_deps(core))
    job = load_class_report_job('job_low', deps=service_deps)
    review_queue = list_class_report_review_queue(teacher_id='teacher_1', deps=service_deps)

    assert result['status'] == 'review'
    assert job['status'] == 'review'
    assert review_queue['items'][0]['report_id'] == 'class_report_low'
    assert review_queue['items'][0]['reason'] == 'low_confidence_bundle'
    assert review_queue['items'][0]['domain'] == 'class_report'
