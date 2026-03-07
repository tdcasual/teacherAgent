from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes.survey_routes import build_router
from services.api.survey_repository import append_survey_review_queue_item, write_survey_bundle, write_survey_report


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"



def test_teacher_survey_report_routes_expose_list_detail_rerun_and_review_queue(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_report(
        "report_1",
        {
            "report_id": "report_1",
            "job_id": "job_1",
            "teacher_id": "teacher_1",
            "class_name": "高二2403班",
            "status": "analysis_ready",
            "confidence": 0.86,
            "summary": "班级整体对实验设计理解偏弱",
            "analysis_artifact": {"executive_summary": "班级整体对实验设计理解偏弱"},
            "bundle_meta": {"parse_confidence": 0.86, "missing_fields": []},
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
            "parse_confidence": 0.86,
            "missing_fields": [],
            "provenance": {"source": "structured"},
        },
        core=core,
    )
    append_survey_review_queue_item(
        {"report_id": "report_1", "teacher_id": "teacher_1", "reason": "low_confidence", "confidence": 0.41},
        core=core,
    )

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        list_res = client.get("/teacher/surveys/reports", params={"teacher_id": "teacher_1"})
        detail_res = client.get("/teacher/surveys/reports/report_1", params={"teacher_id": "teacher_1"})
        rerun_res = client.post(
            "/teacher/surveys/reports/report_1/rerun",
            json={"teacher_id": "teacher_1", "reason": "refresh"},
        )
        review_res = client.get("/teacher/surveys/review-queue", params={"teacher_id": "teacher_1"})

    assert list_res.status_code == 200
    assert list_res.json()["items"][0]["report_id"] == "report_1"
    assert detail_res.status_code == 200
    assert detail_res.json()["report"]["report_id"] == "report_1"
    assert rerun_res.status_code == 200
    assert rerun_res.json()["status"] == "rerun_requested"
    assert review_res.status_code == 200
    assert review_res.json()["items"][0]["reason"] == "low_confidence"
