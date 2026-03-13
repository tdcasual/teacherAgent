from __future__ import annotations

from pathlib import Path

from services.api.job_repository import load_survey_job, write_survey_job
from services.api.multimodal_orchestrator_service import (
    build_multimodal_orchestrator_deps,
    process_multimodal_submission,
)
from services.api.multimodal_report_service import (
    build_multimodal_report_deps,
    list_multimodal_review_queue,
    load_multimodal_report_job,
)
from services.api.multimodal_repository import (
    write_multimodal_extraction,
    write_multimodal_submission,
)
from services.api.survey_orchestrator_service import (
    build_survey_orchestrator_deps,
    process_survey_job,
)
from services.api.survey_repository import read_survey_review_queue, write_survey_raw_payload


class _Core:
    def __init__(self, root: Path, call_llm) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'
        self.call_llm = call_llm
        self.diag_log = lambda *_args, **_kwargs: None



def _multimodal_payload(parse_confidence: float = 0.84) -> dict:
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



def test_survey_domain_disablement_marks_job_failed_without_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('ANALYSIS_DISABLED_DOMAINS', 'survey')
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    write_survey_job(
        'job_disabled',
        {
            'job_id': 'job_disabled',
            'provider': 'provider',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'webhook_received',
            'created_at': '2026-03-06T10:00:00',
        },
        core=core,
    )
    write_survey_raw_payload(
        'job_disabled',
        'provider.json',
        {
            'submission_id': 'sub-disabled',
            'title': '课堂反馈问卷',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'sample_size': 35,
            'questions': [{'id': 'Q1', 'prompt': '本节课难度如何？', 'response_type': 'single_choice', 'stats': {'偏难': 12}}],
        },
        core=core,
    )

    result = process_survey_job('job_disabled', deps=build_survey_orchestrator_deps(core))
    job = load_survey_job('job_disabled', core=core)
    queue = read_survey_review_queue(core=core)

    assert result['status'] == 'failed'
    assert result['error'] == 'analysis_domain_disabled'
    assert job['status'] == 'failed'
    assert job['error'] == 'analysis_domain_disabled'
    assert queue == []



def test_multimodal_review_only_domain_downgrades_to_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('ANALYSIS_REVIEW_ONLY_DOMAINS', 'video_homework')
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    report_deps = build_multimodal_report_deps(core)
    payload = _multimodal_payload(parse_confidence=0.84)
    write_multimodal_submission('submission_1', payload, core=core)
    write_multimodal_extraction('submission_1', payload, core=core)

    result = process_multimodal_submission('submission_1', deps=build_multimodal_orchestrator_deps(core))
    job = load_multimodal_report_job('submission_1', deps=report_deps)
    review_queue = list_multimodal_review_queue(teacher_id='teacher_1', deps=report_deps)

    assert result['status'] == 'review'
    assert job['status'] == 'review'
    assert job['strategy_id'] == 'video_homework.teacher.report'
    assert review_queue['items'][0]['report_id'] == 'submission_1'
    assert review_queue['items'][0]['reason'] == 'domain_review_only'
    assert review_queue['items'][0]['domain'] == 'video_homework'
