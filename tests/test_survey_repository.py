from __future__ import annotations

from pathlib import Path

from services.api.job_repository import load_survey_job, write_survey_job
from services.api.paths import (
    survey_bundle_path,
    survey_job_path,
    survey_raw_payload_dir,
    survey_report_path,
    survey_review_queue_path,
)
from services.api.survey_repository import (
    append_survey_review_queue_item,
    load_survey_bundle,
    load_survey_raw_payload,
    load_survey_report,
    read_survey_review_queue,
    write_survey_bundle,
    write_survey_raw_payload,
    write_survey_report,
)


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"



def test_survey_path_helpers_are_scoped(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    job_path = survey_job_path("survey:job/1", core=core)
    raw_dir = survey_raw_payload_dir("survey:job/1", core=core)
    bundle_path = survey_bundle_path("survey:job/1", core=core)
    report_path = survey_report_path("report:1", core=core)
    queue_path = survey_review_queue_path(core=core)

    assert job_path == core.UPLOADS_DIR / "survey_jobs" / "survey_job_1"
    assert raw_dir == job_path / "raw_payloads"
    assert bundle_path == job_path / "bundle.json"
    assert report_path == core.DATA_DIR / "survey_reports" / "report_1.json"
    assert queue_path == core.DATA_DIR / "survey_review_queue.jsonl"



def test_survey_job_repository_roundtrip(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_job("job_1", {"status": "webhook_received"}, core=core)
    write_survey_job("job_1", {"teacher_id": "teacher_1"}, core=core)

    loaded = load_survey_job("job_1", core=core)
    assert loaded["status"] == "webhook_received"
    assert loaded["teacher_id"] == "teacher_1"
    assert "updated_at" in loaded



def test_survey_repository_persists_raw_payload_bundle_report_and_review_queue(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_raw_payload("job_1", "provider.json", {"provider": "p1"}, core=core)
    write_survey_bundle("job_1", {"survey_meta": {"title": "问卷 1"}}, core=core)
    write_survey_report("report_1", {"summary": "ok"}, core=core)
    append_survey_review_queue_item({"report_id": "report_1", "reason": "low_confidence"}, core=core)

    assert load_survey_raw_payload("job_1", "provider.json", core=core)["provider"] == "p1"
    assert load_survey_bundle("job_1", core=core)["survey_meta"]["title"] == "问卷 1"
    assert load_survey_report("report_1", core=core)["summary"] == "ok"
    queue = read_survey_review_queue(core=core)
    assert queue[-1]["report_id"] == "report_1"
    assert queue[-1]["reason"] == "low_confidence"
