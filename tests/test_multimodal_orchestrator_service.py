from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from services.api.multimodal_orchestrator_service import (
    build_multimodal_orchestrator_deps,
    process_multimodal_submission,
)
from services.api.multimodal_report_service import (
    build_multimodal_report_deps,
    list_multimodal_review_queue,
    load_multimodal_report,
    load_multimodal_report_job,
)
from services.api.multimodal_repository import (
    write_multimodal_extraction,
    write_multimodal_submission,
)
from services.api.specialist_agents.governor import SpecialistAgentRuntimeError


class _Core:
    def __init__(self, root: Path, call_llm) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'
        self.call_llm = call_llm
        self.diag_log = lambda *_args, **_kwargs: None



def _submission_payload(parse_confidence: float = 0.84) -> dict:
    return {
        'source_meta': {
            'source_type': 'video_homework_upload',
            'title': '物理实验讲解',
            'submission_id': 'submission_1',
            'uploaded_at': '2026-03-07T10:00:00',
        },
        'scope': {
            'teacher_id': 'teacher_1',
            'student_id': 'student_1',
            'class_name': '高二2403班',
            'assignment_id': 'assignment_1',
            'submission_kind': 'video_homework',
        },
        'media_files': [
            {
                'file_id': 'video_1',
                'kind': 'video',
                'storage_path': '/tmp/video_1.mp4',
                'mime_type': 'video/mp4',
                'bytes': 2048,
                'duration_sec': 58.0,
            }
        ],
        'transcript_segments': [
            {
                'segment_id': 'asr_1',
                'kind': 'asr',
                'start_sec': 0.0,
                'end_sec': 4.0,
                'text': '首先介绍实验器材与步骤。',
                'confidence': 0.92,
                'evidence_refs': ['segment:asr_1'],
            }
        ],
        'keyframe_evidence': [
            {
                'frame_id': 'frame_1',
                'timestamp_sec': 1.2,
                'image_path': 'derived/frame_1.jpg',
                'ocr_text': '酒精灯与铁架台',
                'confidence': 0.81,
            }
        ],
        'extraction_status': 'completed',
        'parse_confidence': parse_confidence,
        'missing_fields': ['teacher_rubric'],
        'provenance': {'source': 'upload'},
    }



def test_process_multimodal_submission_runs_normal_flow_to_teacher_notified(tmp_path: Path) -> None:
    content = json.dumps(
        {
            'executive_summary': '学生能完整展示实验步骤，但口头表达仍偏简略。',
            'completion_overview': {'status': 'completed', 'summary': '已完成主要实验流程展示。', 'duration_sec': 58.0},
            'expression_signals': [
                {'title': '步骤表达较完整', 'detail': '能够按顺序介绍器材与步骤。', 'evidence_refs': ['segment:asr_1']}
            ],
            'evidence_clips': [
                {'label': '器材介绍', 'start_sec': 0.0, 'end_sec': 4.0, 'evidence_ref': 'segment:asr_1', 'excerpt': '首先介绍实验器材与步骤。'}
            ],
            'teaching_recommendations': ['增加术语表达模板练习。'],
            'confidence_and_gaps': {'confidence': 0.86, 'gaps': ['teacher_rubric']},
        },
        ensure_ascii=False,
    )
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': content}}]})
    report_deps = build_multimodal_report_deps(core)
    write_multimodal_submission('submission_1', _submission_payload(), core=core)
    write_multimodal_extraction('submission_1', _submission_payload(), core=core)

    result = process_multimodal_submission('submission_1', deps=build_multimodal_orchestrator_deps(core))
    job = load_multimodal_report_job('submission_1', deps=report_deps)
    report = load_multimodal_report('submission_1', deps=report_deps)

    assert result['status'] == 'teacher_notified'
    assert job['status'] == 'teacher_notified'
    assert job['strategy_id'] == 'video_homework.teacher.report'
    assert report['status'] == 'analysis_ready'
    assert report['analysis_artifact']['completion_overview']['status'] == 'completed'
    assert report['analysis_artifact']['evidence_clips'][0]['evidence_ref'] == 'segment:asr_1'



def test_process_multimodal_submission_routes_low_confidence_artifact_to_review(tmp_path: Path) -> None:
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    report_deps = build_multimodal_report_deps(core)
    low_conf_payload = _submission_payload(parse_confidence=0.41)
    write_multimodal_submission('submission_1', low_conf_payload, core=core)
    write_multimodal_extraction('submission_1', low_conf_payload, core=core)

    result = process_multimodal_submission('submission_1', deps=build_multimodal_orchestrator_deps(core))
    job = load_multimodal_report_job('submission_1', deps=report_deps)
    review_queue = list_multimodal_review_queue(teacher_id='teacher_1', deps=report_deps)

    assert result['status'] == 'review'
    assert job['status'] == 'review'
    assert review_queue['items'][0]['report_id'] == 'submission_1'
    assert review_queue['items'][0]['reason'] == 'low_confidence_bundle'
    assert review_queue['items'][0]['domain'] == 'video_homework'



def test_process_multimodal_submission_routes_invalid_output_to_review(tmp_path: Path) -> None:
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    report_deps = build_multimodal_report_deps(core)
    payload = _submission_payload(parse_confidence=0.84)
    write_multimodal_submission('submission_invalid', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_invalid'}}, core=core)
    write_multimodal_extraction('submission_invalid', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_invalid'}}, core=core)

    deps = replace(
        build_multimodal_orchestrator_deps(core),
        specialist_runtime=type(
            '_InvalidRuntime',
            (),
            {
                'run': lambda self, _handoff: (_ for _ in ()).throw(
                    SpecialistAgentRuntimeError('invalid_output', 'typed artifact validation failed')
                )
            },
        )(),
    )

    result = process_multimodal_submission('submission_invalid', deps=deps)
    job = load_multimodal_report_job('submission_invalid', deps=report_deps)
    review_queue = list_multimodal_review_queue(teacher_id='teacher_1', deps=report_deps)

    assert result['status'] == 'review'
    assert job['status'] == 'review'
    assert review_queue['items'][0]['report_id'] == 'submission_invalid'
    assert review_queue['items'][0]['reason'] == 'invalid_output'
    assert review_queue['items'][0]['reason_code'] == 'invalid_output'


def test_process_multimodal_submission_uses_controlled_graph_and_verify_failures_downgrade(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    import services.api.multimodal_orchestrator_service as multimodal_orchestrator_service
    from services.api.specialist_agents.contracts import SpecialistAgentResult

    class _CapturingGraphRuntime:
        def __init__(self, *, executor):
            self._executor = executor

        def run(self, graph):
            captured['graph'] = graph
            for node in graph.nodes:
                if node.node_id == 'verify':
                    raise SpecialistAgentRuntimeError('invalid_output', 'verify contract failed')
                self._executor(node.handoff)
            return type(
                '_GraphResult',
                (),
                {
                    'final_result': SpecialistAgentResult(
                        handoff_id='verify',
                        agent_id='video_homework_analyst',
                        status='completed',
                        output={'executive_summary': 'ok'},
                    )
                },
            )()

    monkeypatch.setattr(multimodal_orchestrator_service, 'SpecialistJobGraphRuntime', _CapturingGraphRuntime)

    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    report_deps = build_multimodal_report_deps(core)
    payload = _submission_payload(parse_confidence=0.84)
    write_multimodal_submission('submission_graph', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_graph'}}, core=core)
    write_multimodal_extraction('submission_graph', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_graph'}}, core=core)

    result = process_multimodal_submission('submission_graph', deps=build_multimodal_orchestrator_deps(core))
    job = load_multimodal_report_job('submission_graph', deps=report_deps)
    review_queue = list_multimodal_review_queue(teacher_id='teacher_1', deps=report_deps)

    assert [node.node_id for node in captured['graph'].nodes] == ['analyze', 'verify']
    assert [node.node_type for node in captured['graph'].nodes] == ['analyze', 'verify']
    assert captured['graph'].graph_id == 'video_homework.teacher.report'
    assert result['status'] == 'review'
    assert job['status'] == 'review'
    assert review_queue['items'][0]['report_id'] == 'submission_graph'
    assert review_queue['items'][0]['reason_code'] == 'invalid_output'


def test_process_multimodal_submission_uses_internal_reviewer_and_delivers_primary_artifact(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    import services.api.multimodal_orchestrator_service as multimodal_orchestrator_service
    from services.api.specialist_agents.contracts import SpecialistAgentResult

    class _CapturingGraphRuntime:
        def __init__(self, *, executor):
            self._executor = executor

        def run(self, graph):
            captured['graph'] = graph
            return type(
                '_GraphResult',
                (),
                {
                    'final_result': SpecialistAgentResult(
                        handoff_id='analyze',
                        agent_id='video_homework_analyst',
                        status='completed',
                        output={
                            'executive_summary': 'primary analysis',
                            'completion_overview': {'status': 'completed', 'summary': 'ok'},
                            'key_signals': [],
                            'expression_signals': [],
                            'evidence_clips': [{'label': '器材介绍', 'evidence_ref': 'segment:asr_1'}],
                            'teaching_recommendations': ['增加术语表达模板练习。'],
                            'confidence_and_gaps': {'confidence': 0.86, 'gaps': []},
                        },
                    ),
                    'review_metadata': {
                        'approved': True,
                        'critique_summary': '结构完整，可直接交付。',
                        'reason_codes': [],
                        'recommended_action': 'deliver',
                        'checked_sections': ['executive_summary', 'evidence_clips'],
                    },
                },
            )()

    monkeypatch.setattr(multimodal_orchestrator_service, 'SpecialistJobGraphRuntime', _CapturingGraphRuntime)

    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    report_deps = build_multimodal_report_deps(core)
    payload = _submission_payload(parse_confidence=0.84)
    write_multimodal_submission('submission_reviewer_ok', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_reviewer_ok'}}, core=core)
    write_multimodal_extraction('submission_reviewer_ok', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_reviewer_ok'}}, core=core)

    result = process_multimodal_submission('submission_reviewer_ok', deps=build_multimodal_orchestrator_deps(core))
    report = load_multimodal_report('submission_reviewer_ok', deps=report_deps)

    assert captured['graph'].nodes[0].handoff.to_agent == 'video_homework_analyst'
    assert captured['graph'].nodes[1].handoff.to_agent == 'reviewer_analyst'
    assert result['status'] == 'teacher_notified'
    assert report['analysis_artifact']['executive_summary'] == 'primary analysis'
    assert report['artifact_meta']['review_metadata']['approved'] is True



def test_process_multimodal_submission_routes_reviewer_rejection_to_review_queue(monkeypatch, tmp_path: Path) -> None:
    import services.api.multimodal_orchestrator_service as multimodal_orchestrator_service
    from services.api.specialist_agents.contracts import SpecialistAgentResult

    class _RejectingGraphRuntime:
        def __init__(self, *, executor):
            self._executor = executor

        def run(self, graph):
            return type(
                '_GraphResult',
                (),
                {
                    'final_result': SpecialistAgentResult(
                        handoff_id='analyze',
                        agent_id='video_homework_analyst',
                        status='completed',
                        output={
                            'executive_summary': 'primary analysis',
                            'completion_overview': {'status': 'completed', 'summary': 'ok'},
                            'key_signals': [],
                            'expression_signals': [],
                            'evidence_clips': [],
                            'teaching_recommendations': ['增加术语表达模板练习。'],
                            'confidence_and_gaps': {'confidence': 0.86, 'gaps': []},
                        },
                    ),
                    'review_metadata': {
                        'approved': False,
                        'critique_summary': '缺少证据片段，不能自动直出。',
                        'reason_codes': ['missing_evidence_clips'],
                        'recommended_action': 'enqueue_review',
                        'checked_sections': ['executive_summary', 'evidence_clips'],
                    },
                },
            )()

    monkeypatch.setattr(multimodal_orchestrator_service, 'SpecialistJobGraphRuntime', _RejectingGraphRuntime)

    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    report_deps = build_multimodal_report_deps(core)
    payload = _submission_payload(parse_confidence=0.84)
    write_multimodal_submission('submission_reviewer_reject', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_reviewer_reject'}}, core=core)
    write_multimodal_extraction('submission_reviewer_reject', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_reviewer_reject'}}, core=core)

    result = process_multimodal_submission('submission_reviewer_reject', deps=build_multimodal_orchestrator_deps(core))
    job = load_multimodal_report_job('submission_reviewer_reject', deps=report_deps)
    review_queue = list_multimodal_review_queue(teacher_id='teacher_1', deps=report_deps)

    assert result['status'] == 'review'
    assert job['status'] == 'review'
    assert review_queue['items'][0]['report_id'] == 'submission_reviewer_reject'
    assert review_queue['items'][0]['reason'] == 'missing_evidence_clips'
    assert review_queue['items'][0]['reason_code'] == 'missing_evidence_clips'


def test_process_multimodal_submission_uses_reviewer_v2_schema(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    import services.api.multimodal_orchestrator_service as multimodal_orchestrator_service
    from services.api.specialist_agents.contracts import SpecialistAgentResult

    class _CapturingGraphRuntime:
        def __init__(self, *, executor):
            self._executor = executor

        def run(self, graph):
            captured['graph'] = graph
            return type(
                '_GraphResult',
                (),
                {
                    'final_result': SpecialistAgentResult(
                        handoff_id='analyze',
                        agent_id='video_homework_analyst',
                        status='completed',
                        output={
                            'executive_summary': 'primary analysis',
                            'completion_overview': {'status': 'completed', 'summary': 'ok'},
                            'key_signals': [],
                            'expression_signals': [],
                            'evidence_clips': [{'label': '器材介绍', 'evidence_ref': 'segment:asr_1'}],
                            'teaching_recommendations': ['增加术语表达模板练习。'],
                            'confidence_and_gaps': {'confidence': 0.86, 'gaps': []},
                        },
                    ),
                    'review_metadata': {
                        'approved': True,
                        'critique_summary': '结构完整，可直接交付。',
                        'reason_codes': [],
                        'recommended_action': 'deliver',
                        'checked_sections': ['executive_summary'],
                        'quality_score': 1.0,
                        'issue_list': [],
                    },
                },
            )()

    monkeypatch.setattr(multimodal_orchestrator_service, 'SpecialistJobGraphRuntime', _CapturingGraphRuntime)

    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    payload = _submission_payload(parse_confidence=0.84)
    write_multimodal_submission('submission_reviewer_v2', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_reviewer_v2'}}, core=core)
    write_multimodal_extraction('submission_reviewer_v2', payload | {'source_meta': payload['source_meta'] | {'submission_id': 'submission_reviewer_v2'}}, core=core)

    process_multimodal_submission('submission_reviewer_v2', deps=build_multimodal_orchestrator_deps(core))

    assert captured['graph'].nodes[1].handoff.return_schema['type'] == 'reviewer_critique_v2'
