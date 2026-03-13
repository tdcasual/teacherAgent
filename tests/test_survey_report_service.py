from __future__ import annotations

from pathlib import Path

from services.api.job_repository import write_survey_job
from services.api.survey_report_service import (
    build_survey_report_deps,
    get_survey_report,
    list_survey_reports,
    list_survey_review_queue,
    rerun_survey_report,
)
from services.api.survey_repository import (
    append_survey_review_queue_item,
    write_survey_bundle,
    write_survey_report,
)


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"



def test_list_survey_reports_filters_by_teacher_and_status(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_report(
        "report_1",
        {
            "report_id": "report_1",
            "job_id": "job_report_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "analysis_ready",
            "confidence": 0.86,
            "summary": "班级整体对实验设计理解偏弱",
            "analysis_artifact": {"executive_summary": "班级整体对实验设计理解偏弱"},
            "bundle_meta": {"parse_confidence": 0.86, "missing_fields": []},
            "created_at": "2026-03-06T10:00:00",
            "updated_at": "2026-03-06T10:05:00",
        },
        core=core,
    )
    write_survey_report(
        "report_2",
        {
            "report_id": "report_2",
            "teacher_id": "teacher_2",
            "class_name": "高二2404班",
            "status": "analysis_ready",
            "confidence": 0.73,
        },
        core=core,
    )
    write_survey_job(
        "job_pending_1",
        {
            "job_id": "job_pending_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "bundle_ready",
            "queue_status": "queued",
            "created_at": "2026-03-06T09:00:00",
        },
        core=core,
    )
    write_survey_bundle(
        "job_pending_1",
        {
            "survey_meta": {"title": "课堂反馈问卷", "provider": "provider", "submission_id": "sub-1"},
            "audience_scope": {"teacher_id": "teacher_1", "class_name": "高二2403班", "sample_size": 35},
            "question_summaries": [],
            "group_breakdowns": [],
            "free_text_signals": [],
            "attachments": [],
            "parse_confidence": 0.58,
            "missing_fields": ["question_summaries"],
            "provenance": {"source": "unstructured"},
        },
        core=core,
    )

    deps = build_survey_report_deps(core)
    result = list_survey_reports(teacher_id="teacher_1", status=None, deps=deps)
    ready_only = list_survey_reports(teacher_id="teacher_1", status="analysis_ready", deps=deps)

    assert [item["report_id"] for item in result["items"]] == ["report_1", "job_pending_1"]
    assert all(item["teacher_id"] == "teacher_1" for item in result["items"])
    assert result["items"][1]["confidence"] == 0.58
    assert [item["report_id"] for item in ready_only["items"]] == ["report_1"]



def test_get_survey_report_returns_detail_and_review_flag(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_report(
        "report_1",
        {
            "report_id": "report_1",
            "job_id": "job_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "analysis_ready",
            "confidence": 0.41,
            "summary": "结论可信度偏低，需要复核",
            "analysis_artifact": {"executive_summary": "结论可信度偏低，需要复核"},
            "bundle_meta": {"parse_confidence": 0.41, "missing_fields": ["question_summaries"]},
        },
        core=core,
    )
    write_survey_bundle(
        "job_1",
        {
            "survey_meta": {"title": "课堂反馈问卷", "provider": "provider", "submission_id": "sub-1"},
            "audience_scope": {"teacher_id": "teacher_1", "class_name": "高二2403班", "sample_size": 35},
            "question_summaries": [],
            "group_breakdowns": [],
            "free_text_signals": [],
            "attachments": [],
            "parse_confidence": 0.41,
            "missing_fields": ["question_summaries"],
            "provenance": {"source": "unstructured"},
        },
        core=core,
    )
    append_survey_review_queue_item(
        {"report_id": "report_1", "teacher_id": "teacher_1", "reason": "low_confidence", "confidence": 0.41},
        core=core,
    )

    deps = build_survey_report_deps(core)
    detail = get_survey_report(report_id="report_1", teacher_id="teacher_1", deps=deps)

    assert detail["report"]["report_id"] == "report_1"
    assert detail["report"]["status"] == "analysis_ready"
    assert detail["analysis_artifact"]["executive_summary"] == "结论可信度偏低，需要复核"
    assert detail["bundle_meta"]["parse_confidence"] == 0.41
    assert detail["bundle_meta"]["missing_fields"] == ["question_summaries"]
    assert detail["review_required"] is True



def test_rerun_survey_report_persists_placeholder_request(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_report(
        "report_1",
        {
            "report_id": "report_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "analysis_ready",
        },
        core=core,
    )

    deps = build_survey_report_deps(core)
    result = rerun_survey_report(report_id="report_1", teacher_id="teacher_1", reason="refresh", deps=deps)
    detail = get_survey_report(report_id="report_1", teacher_id="teacher_1", deps=deps)

    assert result["ok"] is True
    assert result["report_id"] == "report_1"
    assert result["status"] == "rerun_requested"
    assert detail["bundle_meta"]["rerun_reason"] == "refresh"
    assert detail["bundle_meta"]["rerun_requested"] is True



def test_list_survey_review_queue_filters_by_teacher(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    append_survey_review_queue_item(
        {"report_id": "report_1", "teacher_id": "teacher_1", "reason": "low_confidence", "confidence": 0.41},
        core=core,
    )
    append_survey_review_queue_item(
        {"report_id": "report_2", "teacher_id": "teacher_2", "reason": "bundle_missing_fields", "confidence": 0.55},
        core=core,
    )

    deps = build_survey_report_deps(core)
    result = list_survey_review_queue(teacher_id="teacher_1", deps=deps)

    assert result["items"] == [
        {
            "report_id": "report_1",
            "teacher_id": "teacher_1",
            "reason": "low_confidence",
            "confidence": 0.41,
            "created_at": None,
        }
    ]
