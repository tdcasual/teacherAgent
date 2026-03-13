from __future__ import annotations

from pathlib import Path

from services.api.survey_repository import read_survey_review_queue
from services.api.survey_review_queue_service import (
    build_survey_review_queue_deps,
    enqueue_survey_review_item,
)


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"



def test_enqueue_survey_review_item_persists_reason_and_confidence(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    item = enqueue_survey_review_item(
        job={"job_id": "job_1", "teacher_id": "teacher_1", "class_name": "高二2403班"},
        reason="low_confidence_bundle",
        confidence=0.55,
        deps=build_survey_review_queue_deps(core),
    )
    queue = read_survey_review_queue(core=core)

    assert item["report_id"] == "job_1"
    assert queue[-1]["teacher_id"] == "teacher_1"
    assert queue[-1]["reason"] == "low_confidence_bundle"
    assert queue[-1]["confidence"] == 0.55


def test_enqueue_survey_review_item_persists_generic_review_defaults(tmp_path: Path) -> None:
    core = _Core(tmp_path)

    item = enqueue_survey_review_item(
        job={'job_id': 'job_2', 'teacher_id': 'teacher_1', 'class_name': '高二2403班'},
        reason='low_confidence_bundle',
        confidence=0.55,
        deps=build_survey_review_queue_deps(core),
    )
    queue = read_survey_review_queue(core=core)

    assert item['domain'] == 'survey'
    assert item['status'] == 'queued'
    assert item['operation'] == 'enqueue'
    assert queue[-1]['domain'] == 'survey'
    assert queue[-1]['status'] == 'queued'
