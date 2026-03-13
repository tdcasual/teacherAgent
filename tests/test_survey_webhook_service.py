from __future__ import annotations

from pathlib import Path

import pytest

from services.api.job_repository import load_survey_job, write_survey_job
from services.api.survey_repository import load_survey_raw_payload, write_survey_raw_payload
from services.api.survey_webhook_service import (
    SurveyWebhookDeps,
    SurveyWebhookError,
    compute_survey_signature,
    ingest_survey_webhook,
)


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / "data"
        self.UPLOADS_DIR = root / "uploads"



def _deps(tmp_path: Path, enqueue_calls: list[str], *, secret: str = "secret") -> SurveyWebhookDeps:
    core = _Core(tmp_path)
    return SurveyWebhookDeps(
        webhook_secret=lambda: secret,
        load_survey_job=lambda job_id: load_survey_job(job_id, core=core),
        write_survey_job=lambda job_id, updates: write_survey_job(job_id, updates, core=core),
        write_survey_raw_payload=lambda job_id, filename, payload: write_survey_raw_payload(job_id, filename, payload, core=core),
        enqueue_survey_job=lambda job_id: enqueue_calls.append(job_id) or {"queued": True, "job_id": job_id},
        now_iso=lambda: "2026-03-06T10:00:00",
        diag_log=lambda _event, _payload: None,
    )



def test_ingest_survey_webhook_accepts_valid_signature_and_enqueues(tmp_path: Path) -> None:
    enqueue_calls: list[str] = []
    payload = {
        "submission_id": "sub-1",
        "teacher_id": "teacher_1",
        "class_name": "高二2403班",
        "title": "课堂反馈问卷",
    }
    deps = _deps(tmp_path, enqueue_calls)
    signature = compute_survey_signature(payload, "secret")

    result = ingest_survey_webhook(
        provider="provider",
        payload=payload,
        signature=signature,
        deps=deps,
    )

    assert result["ok"] is True
    assert result["status"] == "queued"
    assert enqueue_calls == [result["job_id"]]
    assert load_survey_job(result["job_id"], core=_Core(tmp_path))["teacher_id"] == "teacher_1"
    assert load_survey_raw_payload(result["job_id"], "provider.json", core=_Core(tmp_path))["title"] == "课堂反馈问卷"



def test_ingest_survey_webhook_is_idempotent_for_same_submission(tmp_path: Path) -> None:
    enqueue_calls: list[str] = []
    payload = {
        "submission_id": "sub-1",
        "teacher_id": "teacher_1",
        "class_name": "高二2403班",
    }
    deps = _deps(tmp_path, enqueue_calls)
    signature = compute_survey_signature(payload, "secret")

    first = ingest_survey_webhook(provider="provider", payload=payload, signature=signature, deps=deps)
    second = ingest_survey_webhook(provider="provider", payload=payload, signature=signature, deps=deps)

    assert first["job_id"] == second["job_id"]
    assert second["duplicate"] is True
    assert enqueue_calls == [first["job_id"]]



def test_ingest_survey_webhook_rejects_invalid_signature(tmp_path: Path) -> None:
    enqueue_calls: list[str] = []
    payload = {
        "submission_id": "sub-1",
        "teacher_id": "teacher_1",
        "class_name": "高二2403班",
    }
    deps = _deps(tmp_path, enqueue_calls)

    with pytest.raises(SurveyWebhookError, match="invalid_signature"):
        ingest_survey_webhook(provider="provider", payload=payload, signature="sha256=bad", deps=deps)



def test_ingest_survey_webhook_requires_teacher_scope(tmp_path: Path) -> None:
    enqueue_calls: list[str] = []
    payload = {"submission_id": "sub-1", "class_name": "高二2403班"}
    deps = _deps(tmp_path, enqueue_calls)
    signature = compute_survey_signature(payload, "secret")

    with pytest.raises(SurveyWebhookError, match="teacher_scope_missing"):
        ingest_survey_webhook(provider="provider", payload=payload, signature=signature, deps=deps)
