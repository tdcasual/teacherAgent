from __future__ import annotations

import json
from pathlib import Path

from services.api.job_repository import load_survey_job, write_survey_job
from services.api.survey_orchestrator_service import build_survey_orchestrator_deps, process_survey_job
from services.api.survey_repository import (
    load_survey_bundle,
    load_survey_report,
    read_survey_review_queue,
    write_survey_raw_payload,
)


class _Core:
    def __init__(self, root: Path, call_llm) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"
        self.call_llm = call_llm
        self.diag_log = lambda *_args, **_kwargs: None



def test_process_survey_job_runs_normal_flow_to_teacher_notified(tmp_path: Path) -> None:
    content = json.dumps(
        {
            "executive_summary": "班级整体在实验设计题上失分较多。",
            "key_signals": [{"title": "实验设计理解偏弱", "detail": "Q1 中选择偏难的比例较高。", "evidence_refs": ["question:Q1"]}],
            "group_differences": [],
            "teaching_recommendations": ["下节课增加实验设计拆解练习。"],
            "confidence_and_gaps": {"confidence": 0.81, "gaps": []},
        },
        ensure_ascii=False,
    )
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": content}}]})
    write_survey_job(
        "job_1",
        {
            "job_id": "job_1",
            "provider": "provider",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "webhook_received",
            "created_at": "2026-03-06T10:00:00",
        },
        core=core,
    )
    write_survey_raw_payload(
        "job_1",
        "provider.json",
        {
            "submission_id": "sub-1",
            "title": "课堂反馈问卷",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "sample_size": 35,
            "questions": [
                {
                    "id": "Q1",
                    "prompt": "本节课难度如何？",
                    "response_type": "single_choice",
                    "stats": {"偏难": 12, "适中": 20, "偏易": 3},
                }
            ],
            "text_signals": [{"theme": "实验设计", "evidence_count": 6, "excerpts": ["推导太快了"]}],
        },
        core=core,
    )

    result = process_survey_job("job_1", deps=build_survey_orchestrator_deps(core))
    job = load_survey_job("job_1", core=core)
    bundle = load_survey_bundle("job_1", core=core)
    report = load_survey_report("job_1", core=core)

    assert result["status"] == "teacher_notified"
    assert job["status"] == "teacher_notified"
    assert bundle["survey_meta"]["title"] == "课堂反馈问卷"
    assert report["status"] == "analysis_ready"
    assert report["analysis_artifact"]["executive_summary"].startswith("班级整体")



def test_process_survey_job_routes_low_confidence_bundle_to_review(tmp_path: Path) -> None:
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {})
    write_survey_job(
        "job_low",
        {
            "job_id": "job_low",
            "provider": "provider",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "webhook_received",
            "created_at": "2026-03-06T10:00:00",
        },
        core=core,
    )
    write_survey_raw_payload(
        "job_low",
        "provider.json",
        {
            "submission_id": "sub-2",
            "questions": [],
        },
        core=core,
    )

    result = process_survey_job("job_low", deps=build_survey_orchestrator_deps(core))
    job = load_survey_job("job_low", core=core)
    queue = read_survey_review_queue(core=core)

    assert result["status"] == "review"
    assert job["status"] == "review"
    assert queue[-1]["report_id"] == "job_low"
    assert queue[-1]["reason"] == "low_confidence_bundle"


def test_process_survey_job_persists_analysis_report_plane_metadata(tmp_path: Path) -> None:
    content = json.dumps(
        {
            'executive_summary': '班级整体在实验设计题上失分较多。',
            'key_signals': [],
            'group_differences': [],
            'teaching_recommendations': ['下节课增加实验设计拆解练习。'],
            'confidence_and_gaps': {'confidence': 0.81, 'gaps': []},
        },
        ensure_ascii=False,
    )
    core = _Core(tmp_path, call_llm=lambda *_args, **_kwargs: {'choices': [{'message': {'content': content}}]})
    write_survey_job(
        'job_meta',
        {
            'job_id': 'job_meta',
            'provider': 'provider',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'webhook_received',
            'created_at': '2026-03-06T10:00:00',
        },
        core=core,
    )
    write_survey_raw_payload(
        'job_meta',
        'provider.json',
        {
            'submission_id': 'sub-1',
            'title': '课堂反馈问卷',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'sample_size': 35,
            'questions': [{'id': 'Q1', 'prompt': '本节课难度如何？', 'response_type': 'single_choice', 'stats': {'偏难': 12}}],
        },
        core=core,
    )

    process_survey_job('job_meta', deps=build_survey_orchestrator_deps(core))
    report = load_survey_report('job_meta', core=core)

    assert report['analysis_type'] == 'survey'
    assert report['strategy_id'] == 'survey.teacher.report'
    assert report['target_type'] == 'report'
    assert report['target_id'] == 'job_meta'
