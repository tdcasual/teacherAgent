from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path

from services.api.workers.survey_worker_service import (
    SurveyWorkerDeps,
    enqueue_survey_job_inline,
    scan_pending_survey_jobs_inline,
)


def _deps(tmp_path: Path, processed: list[str], failures: list[dict[str, str]]) -> SurveyWorkerDeps:
    return SurveyWorkerDeps(
        job_queue=deque(),
        job_lock=threading.Lock(),
        job_event=threading.Event(),
        job_dir=tmp_path,
        stop_event=threading.Event(),
        worker_started_get=lambda: False,
        worker_started_set=lambda _value: None,
        worker_thread_get=lambda: None,
        worker_thread_set=lambda _value: None,
        process_job=lambda job_id: processed.append(job_id),
        write_job=lambda job_id, updates: failures.append({"job_id": job_id, **{k: str(v) for k, v in updates.items()}}) or updates,
        diag_log=lambda _event, _payload: None,
        sleep=lambda _seconds: None,
        thread_factory=threading.Thread,
        rq_enabled=lambda: False,
    )



def test_enqueue_survey_job_inline_deduplicates(tmp_path: Path) -> None:
    processed: list[str] = []
    failures: list[dict[str, str]] = []
    deps = _deps(tmp_path, processed, failures)

    assert enqueue_survey_job_inline("job_1", deps=deps) is True
    assert enqueue_survey_job_inline("job_1", deps=deps) is False
    assert list(deps.job_queue) == ["job_1"]



def test_scan_pending_survey_jobs_inline_enqueues_jobs(tmp_path: Path) -> None:
    processed: list[str] = []
    failures: list[dict[str, str]] = []
    deps = _deps(tmp_path, processed, failures)
    job_dir = tmp_path / "job_1"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text(json.dumps({"job_id": "job_1", "status": "webhook_received"}), encoding="utf-8")

    count = scan_pending_survey_jobs_inline(deps=deps)

    assert count == 1
    assert list(deps.job_queue) == ["job_1"]
