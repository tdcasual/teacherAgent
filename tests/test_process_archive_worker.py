from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List

import pytest

from services.api.assignment_process_archive_service import (
    AssignmentProcessArchiveDeps,
    ProcessArchiveError,
    freeze_process_archive,
    read_process_archive,
    read_process_archive_summary,
    request_process_archive,
    trigger_on_submit,
    write_pending_skeleton,
)
from services.api.auth_service import AuthPrincipal
from services.api.queue.queue_backend_rq import RqQueueBackend
from services.api.queue.queue_inline_backend import InlineQueueBackend
from services.api.runtime.queue_runtime import enqueue_process_archive
from services.api.student_submit_service import StudentSubmitDeps, submit
from services.api.workers import process_archive_worker_service
from services.api.workers.process_archive_worker_service import (
    enqueue_process_archive_inline,
    run_process_archive_job,
)


async def _save_upload_file(upload: Any, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = getattr(upload, "content", b"1")
    dest.write_bytes(payload)
    return len(payload)


class _Upload:
    def __init__(self, filename: str, content: bytes = b"1") -> None:
        self.filename = filename
        self.content = content

    async def read(self, size: int = -1) -> bytes:
        if size is None or int(size) < 0:
            raise AssertionError("full read() is forbidden")
        return self.content[: int(size)] if int(size) else b""


def _progress(*, submitted: bool = True) -> Dict[str, Any]:
    return {
        "ok": True,
        "students": [
            {
                "student_id": "S1",
                "evidence": {
                    "schema": "assignment_progress_evidence/v1",
                    "signals": {
                        "submitted": submitted,
                        "best_graded_total": 10 if submitted else 0,
                        "best_score_earned": 8.0 if submitted else 0,
                        "best_attempt_id": "submission_ok",
                        "min_graded_total": 1,
                    },
                },
            }
        ],
    }


def _archive_deps(root: Path, **overrides: Any) -> AssignmentProcessArchiveDeps:
    assignment_dir = root / "assignments" / "HW_1"
    assignment_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "assignment_id": "HW_1",
        "teacher_id": "t_zhang",
        "subject_id": "physics",
        "visibility_status": "published",
        "expected_students": ["S1"],
    }
    fields: Dict[str, Any] = dict(
        data_dir=root,
        load_assignment_meta=lambda _folder: dict(meta),
        load_student_sessions=lambda _student_id, _assignment_id: [],
        load_session_turns=lambda _student_id, _session_id: [],
        call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": "{}"}}]},
        now_iso=lambda: "2026-08-28T12:00:00",
        diag_log=lambda _event, _payload: None,
        monotonic=lambda: 0.0,
        new_id=lambda: "parch_test1",
    )
    fields.update(overrides)
    return AssignmentProcessArchiveDeps(**fields)


def _worker_deps(**overrides: Any) -> process_archive_worker_service.ProcessArchiveWorkerDeps:
    queue: deque = deque()
    event = threading.Event()
    stop_event = threading.Event()
    started = {"value": False}
    thread_holder: Dict[str, Any] = {"thread": None}
    logs: List[tuple] = []
    fields: Dict[str, Any] = dict(
        update_queue=queue,
        update_lock=threading.Lock(),
        update_event=event,
        stop_event=stop_event,
        worker_started_get=lambda: started["value"],
        worker_started_set=lambda value: started.__setitem__("value", bool(value)),
        worker_thread_get=lambda: thread_holder["thread"],
        worker_thread_set=lambda value: thread_holder.__setitem__("thread", value),
        queue_max=32,
        freeze_process_archive=lambda _payload: {"status": "frozen"},
        diag_log=lambda event, payload: logs.append((event, dict(payload or {}))),
        sleep=lambda _seconds: stop_event.set(),
        thread_factory=lambda **_kwargs: None,
        rq_enabled=lambda: False,
        monotonic=lambda: 0.0,
    )
    fields.update(overrides)
    deps = process_archive_worker_service.ProcessArchiveWorkerDeps(**fields)
    return deps


def _submit_deps(root: Path, **overrides: Any) -> StudentSubmitDeps:
    fields = dict(
        uploads_dir=root / "uploads",
        app_root=root / "repo",
        student_submissions_dir=root / "submissions",
        run_script=lambda _args: "ok",
        compute_assignment_progress=lambda _assignment_id, _include_students: _progress(),
        student_memory_auto_propose_from_assignment_evidence=lambda **_kwargs: {
            "ok": False,
            "created": False,
        },
        load_assignment_teacher_id=lambda _assignment_id: "t_zhang",
        diag_log=lambda _event, _payload: None,
        save_upload_file=_save_upload_file,
        trigger_process_archive=None,
    )
    fields.update(overrides)
    return StudentSubmitDeps(**fields)


def _archive_path(root: Path, assignment_id: str = "HW_1", student_id: str = "S1") -> Path:
    return root / "assignments" / assignment_id / "process_archives" / f"{student_id}.json"


def test_handlers_do_not_call_enqueue_inline_directly() -> None:
    banned = "enqueue_process_archive_inline"
    for rel in (
        "services/api/student_submit_service.py",
        "services/api/routes/student_ops_routes.py",
        "services/api/routes/student_history_routes.py",
    ):
        source = Path(rel).read_text(encoding="utf-8")
        assert banned not in source


def test_queue_backends_expose_enqueue_process_archive() -> None:
    backend = InlineQueueBackend(
        enqueue_upload_job_fn=lambda _job_id: None,
        enqueue_profile_update_fn=lambda _payload: None,
        enqueue_process_archive_fn=lambda _payload: None,
        enqueue_chat_job_fn=lambda _job_id, _lane_id=None: {},
        scan_pending_upload_jobs_fn=lambda: 0,
        scan_pending_chat_jobs_fn=lambda: 0,
        start_fn=lambda: None,
        stop_fn=lambda: None,
    )
    captured: List[Dict[str, Any]] = []
    backend.enqueue_process_archive_fn = captured.append  # type: ignore[method-assign]
    enqueue_process_archive({"assignment_id": "HW_1", "student_id": "S1"}, backend=backend)
    assert captured == [{"assignment_id": "HW_1", "student_id": "S1"}]
    assert hasattr(RqQueueBackend, "enqueue_process_archive")
    assert not hasattr(backend, "enqueue_exam_job")
    assert not hasattr(backend, "enqueue_survey_job")
    assert not hasattr(RqQueueBackend, "enqueue_exam_job")
    assert not hasattr(RqQueueBackend, "enqueue_survey_job")


def test_submit_writes_pending_and_enqueues() -> None:
    asyncio.run(_submit_writes_pending_and_enqueues())


async def _submit_writes_pending_and_enqueues() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        enqueued: List[Dict[str, Any]] = []
        archive_deps = _archive_deps(root)
        llm_calls = {"n": 0}

        def _call_llm(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            llm_calls["n"] += 1
            raise AssertionError("submit must not run process-archive LLM")

        archive_deps = _archive_deps(root, call_llm=_call_llm)

        def _trigger(*, assignment_id: str, student_id: str, reason: str = "submit") -> Dict[str, Any]:
            return trigger_on_submit(
                assignment_id=assignment_id,
                student_id=student_id,
                reason=reason,
                deps=archive_deps,
                enqueue=enqueued.append,
            )

        result = await submit(
            student_id="S1",
            files=[_Upload("a1.pdf")],
            assignment_id="HW_1",
            auto_assignment=False,
            deps=_submit_deps(root, trigger_process_archive=_trigger),
        )
        assert result["ok"] is True
        assert result["submitted"] is True
        assert result["process_archive_status"] == "pending"
        assert result["process_archive_id"]
        assert llm_calls["n"] == 0
        assert len(enqueued) == 1
        payload = enqueued[0]
        assert payload["assignment_id"] == "HW_1"
        assert payload["student_id"] == "S1"
        assert payload["reason"] == "submit"
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["schema"] == "assignment_process_archive/v1"
        assert saved["status"] == "pending"
        assert saved["frozen_reason"] == "submit"


def test_submit_queue_full_keeps_pending_and_returns_ok() -> None:
    asyncio.run(_submit_queue_full_keeps_pending_and_returns_ok())


async def _submit_queue_full_keeps_pending_and_returns_ok() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        logs: List[tuple] = []
        worker_deps = _worker_deps(
            queue_max=0,
            diag_log=lambda event, payload: logs.append((event, dict(payload or {}))),
        )
        archive_deps = _archive_deps(root)

        def _trigger(*, assignment_id: str, student_id: str, reason: str = "submit") -> Dict[str, Any]:
            return trigger_on_submit(
                assignment_id=assignment_id,
                student_id=student_id,
                reason=reason,
                deps=archive_deps,
                enqueue=lambda payload: enqueue_process_archive_inline(payload, deps=worker_deps),
            )

        result = await submit(
            student_id="S1",
            files=[_Upload("a1.pdf")],
            assignment_id="HW_1",
            auto_assignment=False,
            deps=_submit_deps(root, trigger_process_archive=_trigger),
        )
        assert result["ok"] is True
        assert result["submitted"] is True
        assert result["process_archive_status"] == "pending"
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["status"] == "pending"
        assert any(event == "process_archive.queue_full" for event, _payload in logs)
        assert len(worker_deps.update_queue) == 0


def test_enqueue_process_archive_inline_queue_full_keeps_pending() -> None:
    logs: List[tuple] = []
    deps = _worker_deps(
        queue_max=0,
        diag_log=lambda event, payload: logs.append((event, dict(payload or {}))),
    )
    enqueue_process_archive_inline(
        {"assignment_id": "HW_1", "student_id": "S1"},
        deps=deps,
    )
    assert list(deps.update_queue) == []
    assert logs[0][0] == "process_archive.queue_full"
    assert logs[0][1]["assignment_id"] == "HW_1"
    assert logs[0][1]["student_id"] == "S1"


def test_inline_worker_pending_to_frozen_without_sessions() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        pending = write_pending_skeleton(
            assignment_id="HW_1",
            student_id="S1",
            reason="submit",
            deps=archive_deps,
        )
        processed: List[Dict[str, Any]] = []

        def _freeze(payload: Dict[str, Any]) -> Dict[str, Any]:
            result = freeze_process_archive(payload, deps=archive_deps)
            processed.append(result)
            return result

        worker_deps = _worker_deps(freeze_process_archive=_freeze, queue_max=8)
        enqueue_process_archive_inline(
            {
                "assignment_id": "HW_1",
                "student_id": "S1",
                "reason": "submit",
                "process_archive_id": pending["job_id"],
                "job_id": pending["job_id"],
            },
            deps=worker_deps,
        )
        run_process_archive_job(worker_deps.update_queue.popleft(), deps=worker_deps)
        assert processed[0]["status"] == "frozen"
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["status"] == "frozen"
        assert saved["quotes"] == []
        assert saved["session_ids"] == []


def test_inline_worker_pending_to_partial_on_llm_timeout() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)

        def _call_llm(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            raise TimeoutError("llm 20s")

        turns = [
            {
                "role": "user",
                "content": "我觉得加速度和速度是一回事",
                "ts": "2026-08-28T11:40:12",
            }
        ]
        archive_deps = _archive_deps(
            root,
            call_llm=_call_llm,
            load_student_sessions=lambda _sid, _aid: ["ses_abc"],
            load_session_turns=lambda _sid, _session_id: turns,
        )
        write_pending_skeleton(
            assignment_id="HW_1",
            student_id="S1",
            reason="submit",
            deps=archive_deps,
        )
        worker_deps = _worker_deps(
            freeze_process_archive=lambda payload: freeze_process_archive(payload, deps=archive_deps),
        )
        run_process_archive_job(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit", "job_id": "parch_test1"},
            deps=worker_deps,
        )
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["status"] == "partial"
        assert saved["quotes"]
        assert saved["quotes"][0]["text"] == "我觉得加速度和速度是一回事"


def test_timeout_writes_partial_without_raise() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)

        def _boom(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            raise TimeoutError("worker 60s")

        archive_deps = _archive_deps(
            root,
            call_llm=_boom,
            load_student_sessions=lambda _sid, _aid: ["ses_abc"],
            load_session_turns=lambda _sid, _session_id: [
                {"role": "user", "content": "卡在单位", "ts": "2026-08-28T11:00:00"}
            ],
        )
        write_pending_skeleton(
            assignment_id="HW_1", student_id="S1", reason="submit", deps=archive_deps
        )
        logs: List[tuple] = []
        worker_deps = _worker_deps(
            freeze_process_archive=lambda payload: freeze_process_archive(payload, deps=archive_deps),
            diag_log=lambda event, payload: logs.append((event, dict(payload or {}))),
        )
        run_process_archive_job(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
            deps=worker_deps,
        )
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["status"] == "partial"


def test_rq_retry_does_not_overwrite_frozen() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        write_pending_skeleton(
            assignment_id="HW_1", student_id="S1", reason="submit", deps=archive_deps
        )
        first = freeze_process_archive(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
            deps=archive_deps,
        )
        assert first["status"] == "frozen"
        mutated_deps = _archive_deps(
            root,
            call_llm=lambda *_a, **_k: {
                "choices": [{"message": {"content": json.dumps({"quotes": [{"text": "retry"}]})}}]
            },
            load_student_sessions=lambda *_a, **_k: ["ses_new"],
            now_iso=lambda: "2026-08-29T00:00:00",
        )
        second = freeze_process_archive(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
            deps=mutated_deps,
        )
        assert second["status"] == "frozen"
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["frozen_at"] == first["frozen_at"]
        assert saved["quotes"] == []


def test_pii_filter_drops_blocked_quotes() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        turns = [
            {"role": "user", "content": "手机号13812345678别告诉老师", "ts": "2026-08-28T11:40:12"},
            {"role": "user", "content": "我觉得加速度和速度是一回事", "ts": "2026-08-28T11:41:00"},
        ]
        archive_deps = _archive_deps(
            root,
            load_student_sessions=lambda *_a, **_k: ["ses_abc"],
            load_session_turns=lambda *_a, **_k: turns,
            call_llm=lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("skip llm")),
        )
        write_pending_skeleton(
            assignment_id="HW_1", student_id="S1", reason="submit", deps=archive_deps
        )
        freeze_process_archive(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
            deps=archive_deps,
        )
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        texts = [item.get("text") for item in saved.get("quotes") or []]
        assert "我觉得加速度和速度是一回事" in texts
        assert all("13812345678" not in str(text) for text in texts)


def test_pii_filter_drops_blocked_stuck_points_from_llm() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        payload = {
            "quotes": [
                {
                    "text": "我觉得加速度和速度是一回事",
                    "turn_ref": "ses_abc:1",
                    "speaker": "student",
                }
            ],
            "stuck_points": [
                {"summary": "手机号13812345678", "evidence_refs": ["ses_abc:1"]},
                {"summary": "把 v 与 a 混用", "evidence_refs": ["ses_abc:1"]},
            ],
            "reasoning_types": ["unit_confusion", "成绩 90"],
            "coach_comment_excerpts": [
                {"text": "身份证号110101199001011234", "turn_ref": "ses_abc:2"}
            ],
        }

        def _llm(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

        archive_deps = _archive_deps(
            root,
            load_student_sessions=lambda *_a, **_k: ["ses_abc"],
            load_session_turns=lambda *_a, **_k: [
                {"role": "user", "content": "我觉得加速度和速度是一回事", "ts": "2026-08-28T11:41:00"}
            ],
            call_llm=_llm,
        )
        write_pending_skeleton(
            assignment_id="HW_1", student_id="S1", reason="submit", deps=archive_deps
        )
        freeze_process_archive(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
            deps=archive_deps,
        )
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        summaries = [str(item.get("summary") or "") for item in saved.get("stuck_points") or []]
        assert "把 v 与 a 混用" in summaries
        blob = json.dumps(saved, ensure_ascii=False)
        assert "13812345678" not in blob
        assert "110101199001011234" not in blob
        assert "成绩 90" not in blob
        summary = read_process_archive_summary(root, "HW_1", "S1")
        summary_text = json.dumps(summary, ensure_ascii=False)
        assert "13812345678" not in summary_text
        assert "把 v 与 a 混用" in summary_text


def test_hung_llm_does_not_block_freeze_past_budget() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        release = threading.Event()

        def _hang(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            release.wait(timeout=30)
            return {"choices": [{"message": {"content": "{}"}}]}

        archive_deps = _archive_deps(
            root,
            call_llm=_hang,
            monotonic=time.monotonic,
            load_student_sessions=lambda *_a, **_k: ["ses_abc"],
            load_session_turns=lambda *_a, **_k: [
                {"role": "user", "content": "卡点", "ts": "2026-08-28T11:00:00"}
            ],
        )
        write_pending_skeleton(
            assignment_id="HW_1", student_id="S1", reason="submit", deps=archive_deps
        )
        started = time.monotonic()
        try:
            result = freeze_process_archive(
                {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
                deps=archive_deps,
                deadline=time.monotonic() + 0.15,
            )
            elapsed = time.monotonic() - started
            assert elapsed < 2.0
            assert result["status"] == "partial"
            saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
            assert saved["status"] == "partial"
        finally:
            release.set()


def test_request_process_archive_sync_timeout_keeps_pending_and_enqueues() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        enqueued: List[Dict[str, Any]] = []

        def _slow_llm(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            raise TimeoutError("sync 15s")

        clock = {"t": 0.0}

        def _monotonic() -> float:
            clock["t"] += 20.0
            return clock["t"]

        archive_deps = _archive_deps(
            root,
            call_llm=_slow_llm,
            monotonic=_monotonic,
            load_student_sessions=lambda *_a, **_k: ["ses_abc"],
            load_session_turns=lambda *_a, **_k: [
                {"role": "user", "content": "卡点", "ts": "2026-08-28T11:00:00"}
            ],
        )
        result = request_process_archive(
            assignment_id="HW_1",
            student_id="S1",
            reason="manual",
            principal=AuthPrincipal(actor_id="S1", role="student"),
            deps=archive_deps,
            enqueue=enqueued.append,
            sync_timeout_sec=15,
        )
        assert result["http_status"] == 202
        assert result["status"] == "pending"
        assert result["process_archive_id"]
        assert enqueued
        saved = read_process_archive(root, "HW_1", "S1")
        assert saved is not None
        assert saved["status"] == "pending"


def test_request_process_archive_rejects_cross_student() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        with pytest.raises(ProcessArchiveError) as ctx:
            request_process_archive(
                assignment_id="HW_1",
                student_id="S1",
                reason="manual",
                principal=AuthPrincipal(actor_id="S2", role="student"),
                deps=archive_deps,
                enqueue=lambda _payload: None,
            )
        assert ctx.value.status_code == 403
        assert not _archive_path(root).exists()


def test_request_process_archive_rejects_non_owner_teacher() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        with pytest.raises(ProcessArchiveError) as ctx:
            request_process_archive(
                assignment_id="HW_1",
                student_id="S1",
                reason="manual",
                principal=AuthPrincipal(actor_id="t_other", role="teacher"),
                deps=archive_deps,
                enqueue=lambda _payload: None,
            )
        assert ctx.value.status_code == 403
        assert ctx.value.detail == "forbidden_assignment_owner"
        assert not _archive_path(root).exists()


def test_request_process_archive_missing_assignment_404() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        with pytest.raises(ProcessArchiveError) as ctx:
            request_process_archive(
                assignment_id="missing",
                student_id="S1",
                reason="manual",
                principal=AuthPrincipal(actor_id="S1", role="student"),
                deps=archive_deps,
                enqueue=lambda _payload: None,
            )
        assert ctx.value.status_code == 404
        assert not (root / "assignments" / "missing" / "process_archives" / "S1.json").exists()


def test_request_process_archive_rejects_unpublished_student() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(
            root,
            load_assignment_meta=lambda _folder: {
                "assignment_id": "HW_1",
                "teacher_id": "t_zhang",
                "subject_id": "physics",
                "visibility_status": "draft",
                "expected_students": ["S1"],
            },
        )
        with pytest.raises(ProcessArchiveError) as ctx:
            request_process_archive(
                assignment_id="HW_1",
                student_id="S1",
                reason="manual",
                principal=AuthPrincipal(actor_id="S1", role="student"),
                deps=archive_deps,
                enqueue=lambda _payload: None,
            )
        assert ctx.value.status_code == 403
        assert ctx.value.detail == "forbidden_assignment_scope"
        assert not _archive_path(root).exists()


def test_request_process_archive_anonymous_is_401() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        with pytest.raises(ProcessArchiveError) as ctx:
            request_process_archive(
                assignment_id="HW_1",
                student_id="S1",
                reason="manual",
                principal=None,
                deps=archive_deps,
                enqueue=lambda _payload: None,
            )
        assert ctx.value.status_code == 401
        assert ctx.value.detail == "missing_authorization"
        assert not _archive_path(root).exists()


def test_request_process_archive_allows_owner_teacher() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        archive_deps = _archive_deps(root)
        result = request_process_archive(
            assignment_id="HW_1",
            student_id="S1",
            reason="manual",
            principal=AuthPrincipal(actor_id="t_zhang", role="teacher"),
            deps=archive_deps,
            enqueue=lambda _payload: None,
            sync_timeout_sec=15,
        )
        assert result["status"] in {"frozen", "pending"}
        assert result.get("http_status") in {200, 202}


def test_rq_run_process_archive_does_not_raise_after_partial() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)

        def _boom(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
            raise TimeoutError("llm")

        archive_deps = _archive_deps(
            root,
            call_llm=_boom,
            load_student_sessions=lambda *_a, **_k: ["ses_abc"],
            load_session_turns=lambda *_a, **_k: [
                {"role": "user", "content": "单位搞混了", "ts": "2026-08-28T11:00:00"}
            ],
        )
        write_pending_skeleton(
            assignment_id="HW_1", student_id="S1", reason="submit", deps=archive_deps
        )

        def _freeze(payload: Dict[str, Any]) -> Dict[str, Any]:
            return freeze_process_archive(payload, deps=archive_deps)

        worker_deps = _worker_deps(freeze_process_archive=_freeze)
        run_process_archive_job(
            {"assignment_id": "HW_1", "student_id": "S1", "reason": "submit"},
            deps=worker_deps,
        )
        saved = json.loads(_archive_path(root).read_text(encoding="utf-8"))
        assert saved["status"] == "partial"


def test_rq_enqueue_process_archive_has_60s_timeout_and_no_retry() -> None:
    source = Path("services/api/workers/rq_tasks.py").read_text(encoding="utf-8")
    start = source.index("def enqueue_process_archive")
    end = source.index("\ndef ", start + 1)
    body = source[start:end]
    assert "PROCESS_ARCHIVE_JOB_TIMEOUT = 60" in source
    assert "job_timeout=PROCESS_ARCHIVE_JOB_TIMEOUT" in body
    assert "retry=" not in body
    assert "_enqueue_retry_job" not in body
