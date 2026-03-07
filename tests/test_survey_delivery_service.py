from __future__ import annotations

from pathlib import Path

from services.api.job_repository import write_survey_job
from services.api.survey_delivery_service import build_survey_delivery_deps, deliver_survey_report
from services.api.survey_repository import load_survey_report


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"



def test_deliver_survey_report_persists_teacher_visible_report(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    job = write_survey_job(
        "job_1",
        {
            "job_id": "job_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "analysis_ready",
            "created_at": "2026-03-06T10:00:00",
        },
        core=core,
    )
    bundle = {
        "survey_meta": {"title": "课堂反馈问卷", "provider": "provider", "submission_id": "sub-1"},
        "audience_scope": {"teacher_id": "teacher_1", "class_name": "高二2403班", "sample_size": 35},
        "question_summaries": [],
        "group_breakdowns": [],
        "free_text_signals": [],
        "attachments": [],
        "parse_confidence": 0.78,
        "missing_fields": ["student_level_raw_data"],
        "provenance": {"source": "merged"},
    }
    analysis_artifact = {
        "executive_summary": "班级整体在实验设计题上失分较多。",
        "key_signals": [{"title": "实验设计理解偏弱", "detail": "Q1 中选择偏难的比例较高。", "evidence_refs": ["question:Q1"]}],
        "group_differences": [],
        "teaching_recommendations": ["下节课增加实验设计拆解练习。"],
        "confidence_and_gaps": {"confidence": 0.81, "gaps": ["student_level_raw_data"]},
    }

    report = deliver_survey_report(job=job, bundle=bundle, analysis_artifact=analysis_artifact, deps=build_survey_delivery_deps(core))
    stored = load_survey_report("job_1", core=core)

    assert report["report_id"] == "job_1"
    assert stored["summary"] == "班级整体在实验设计题上失分较多。"
    assert stored["bundle_meta"]["parse_confidence"] == 0.78
    assert stored["rendered_markdown"].startswith("# 问卷分析报告")
