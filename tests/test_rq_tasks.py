from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from services.api.workers import rq_tasks


class _FakeQueue:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def enqueue(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})


class _FakeRedis:
    def __init__(self, *, fail_ping: bool = False) -> None:
        self.fail_ping = fail_ping

    def ping(self) -> None:
        if self.fail_ping:
            raise RuntimeError("ping failed")


def test_queue_name_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RQ_QUEUE_NAME", raising=False)
    assert rq_tasks._queue_name() == "default"

    monkeypatch.setenv("RQ_QUEUE_NAME", "critical")
    assert rq_tasks._queue_name() == "critical"


def test_require_redis_client_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="Redis required: REDIS_URL not set"):
        rq_tasks._require_redis_client(decode_responses=False)


def test_require_redis_client_wraps_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    def _fake_get(_url: str, *, decode_responses: bool) -> _FakeRedis:
        assert decode_responses is True
        return _FakeRedis(fail_ping=True)

    monkeypatch.setattr(rq_tasks, "get_redis_client", _fake_get)

    with pytest.raises(RuntimeError, match="unable to connect"):
        rq_tasks._require_redis_client(decode_responses=True)


def test_require_redis_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(
        rq_tasks,
        "get_redis_client",
        lambda _url, *, decode_responses: _FakeRedis(),
    )
    rq_tasks.require_redis()


def test_get_queue_uses_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("RQ_QUEUE_NAME", "jobs")

    monkeypatch.setattr(
        rq_tasks,
        "get_redis_client",
        lambda _url, *, decode_responses: _FakeRedis(),
    )

    captured: Dict[str, Any] = {}

    class _QueueCtor:
        def __init__(self, name: str, connection: Any) -> None:
            captured["name"] = name
            captured["connection"] = connection

    monkeypatch.setattr(rq_tasks, "Queue", _QueueCtor)

    queue = rq_tasks._get_queue()
    assert captured["name"] == "jobs"
    assert isinstance(captured["connection"], _FakeRedis)
    assert isinstance(queue, _QueueCtor)


def test_lane_store_uses_tenant_fallback_and_mod_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(
        rq_tasks,
        "_require_redis_client",
        lambda *, decode_responses: {"decode": decode_responses},
    )

    captured: Dict[str, Any] = {}

    class _FakeLaneStore:
        def __init__(
            self,
            *,
            redis_client: Any,
            tenant_id: str,
            claim_ttl_sec: int,
            debounce_ms: int,
        ) -> None:
            captured["redis_client"] = redis_client
            captured["tenant_id"] = tenant_id
            captured["claim_ttl_sec"] = claim_ttl_sec
            captured["debounce_ms"] = debounce_ms

    monkeypatch.setattr(rq_tasks, "ChatRedisLaneStore", _FakeLaneStore)
    mod = SimpleNamespace(TENANT_ID="tenant-from-mod", CHAT_JOB_CLAIM_TTL_SEC=321, CHAT_LANE_DEBOUNCE_MS=45)

    rq_tasks._lane_store(mod, tenant_id=None)

    assert captured["redis_client"] == {"decode": True}
    assert captured["tenant_id"] == "tenant-from-mod"
    assert captured["claim_ttl_sec"] == 321
    assert captured["debounce_ms"] == 45


def test_enqueue_basic_jobs_use_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)

    rq_tasks.enqueue_upload_job("up-1", tenant_id="t1")
    rq_tasks.enqueue_exam_job("exam-1", tenant_id="t2")
    rq_tasks.enqueue_profile_update({"uid": "u-1"}, tenant_id="t3")

    assert queue.calls[0]["func"] is rq_tasks.run_upload_job
    assert queue.calls[0]["args"] == ("up-1",)
    assert queue.calls[0]["kwargs"] == {"tenant_id": "t1"}

    assert queue.calls[1]["func"] is rq_tasks.run_exam_job
    assert queue.calls[1]["args"] == ("exam-1",)
    assert queue.calls[1]["kwargs"] == {"tenant_id": "t2"}

    assert queue.calls[2]["func"] is rq_tasks.run_profile_update
    assert queue.calls[2]["args"] == ()
    assert queue.calls[2]["kwargs"] == {"payload": {"uid": "u-1"}, "tenant_id": "t3"}


def test_enqueue_chat_job_resolves_lane_and_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    store = SimpleNamespace(enqueue=lambda job_id, lane_id: ({"lane_queue_position": 2}, True))
    mod = SimpleNamespace(
        load_chat_job=lambda job_id: {"job_id": job_id, "lane": "L-1"},
        resolve_chat_lane_id_from_job=lambda job: "L-1",
    )

    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: store)
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)

    result = rq_tasks.enqueue_chat_job("chat-1", lane_id=None, tenant_id="tenant-a")

    assert result == {"lane_id": "L-1", "lane_queue_position": 2}
    assert len(queue.calls) == 1
    assert queue.calls[0]["func"] is rq_tasks.run_chat_job
    assert queue.calls[0]["args"] == ("chat-1", "L-1")
    assert queue.calls[0]["kwargs"] == {"tenant_id": "tenant-a"}


def test_enqueue_chat_job_fallback_lane_and_no_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SimpleNamespace(enqueue=lambda job_id, lane_id: ({"lane_queue_position": 0}, False))
    mod = SimpleNamespace(
        load_chat_job=lambda _job_id: (_ for _ in ()).throw(RuntimeError("boom")),
        resolve_chat_lane_id_from_job=lambda job: "unused",
    )

    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: store)

    get_queue_called = {"called": False}

    def _queue_unexpected() -> _FakeQueue:
        get_queue_called["called"] = True
        return _FakeQueue()

    monkeypatch.setattr(rq_tasks, "_get_queue", _queue_unexpected)

    result = rq_tasks.enqueue_chat_job("chat-2", lane_id="", tenant_id="tenant-a")

    assert result["lane_id"] == "unknown:session_main:req_unknown"
    assert get_queue_called["called"] is False


def _write_job(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def test_scan_pending_upload_jobs_enqueues_valid_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    job_dir = tmp_path / "upload_jobs"
    mod = SimpleNamespace(UPLOAD_JOB_DIR=job_dir)
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)

    called: List[str] = []
    monkeypatch.setattr(rq_tasks, "enqueue_upload_job", lambda job_id, *, tenant_id=None: called.append(job_id))

    _write_job(job_dir / "a" / "job.json", '{"status":"queued","job_id":"u-1"}')
    _write_job(job_dir / "b" / "job.json", '{"status":"processing","job_id":"u-2"}')
    _write_job(job_dir / "c" / "job.json", '{"status":"done","job_id":"u-3"}')
    _write_job(job_dir / "d" / "job.json", '{"status":"queued","job_id":""}')
    _write_job(job_dir / "e" / "job.json", '{bad-json')

    assert rq_tasks.scan_pending_upload_jobs(tenant_id="t") == 2
    assert called == ["u-1", "u-2"]


def test_scan_pending_exam_jobs_enqueues_valid_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    job_dir = tmp_path / "exam_jobs"
    mod = SimpleNamespace(EXAM_UPLOAD_JOB_DIR=job_dir)
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)

    called: List[str] = []
    monkeypatch.setattr(rq_tasks, "enqueue_exam_job", lambda job_id, *, tenant_id=None: called.append(job_id))

    _write_job(job_dir / "a" / "job.json", '{"status":"queued","job_id":"e-1"}')
    _write_job(job_dir / "b" / "job.json", '{"status":"processing","job_id":"e-2"}')
    _write_job(job_dir / "c" / "job.json", '{"status":"failed","job_id":"e-3"}')

    assert rq_tasks.scan_pending_exam_jobs(tenant_id="t") == 2
    assert called == ["e-1", "e-2"]


def test_scan_pending_chat_jobs_resolves_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    job_dir = tmp_path / "chat_jobs"
    mod = SimpleNamespace(
        CHAT_JOB_DIR=job_dir,
        resolve_chat_lane_id_from_job=lambda job: f"lane:{job.get('job_id')}",
    )
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)

    called: List[Dict[str, str]] = []

    def _enqueue_chat(job_id: str, lane_id: str | None = None, *, tenant_id: str | None = None) -> Dict[str, Any]:
        called.append({"job_id": job_id, "lane_id": str(lane_id)})
        return {}

    monkeypatch.setattr(rq_tasks, "enqueue_chat_job", _enqueue_chat)

    _write_job(job_dir / "a" / "job.json", '{"status":"queued","job_id":"c-1"}')
    _write_job(job_dir / "b" / "job.json", '{"status":"processing","job_id":"c-2"}')
    _write_job(job_dir / "c" / "job.json", '{"status":"done","job_id":"c-3"}')

    assert rq_tasks.scan_pending_chat_jobs(tenant_id="t") == 2
    assert called == [
        {"job_id": "c-1", "lane_id": "lane:c-1"},
        {"job_id": "c-2", "lane_id": "lane:c-2"},
    ]


def test_run_handlers_dispatch_to_tenant_module(monkeypatch: pytest.MonkeyPatch) -> None:
    called: Dict[str, Any] = {}

    mod = SimpleNamespace(
        process_upload_job=lambda job_id: called.__setitem__("upload", job_id),
        process_exam_upload_job=lambda job_id: called.__setitem__("exam", job_id),
        student_profile_update=lambda payload: called.__setitem__("profile", payload),
    )
    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)

    rq_tasks.run_upload_job("u-10", tenant_id="t")
    rq_tasks.run_exam_job("e-10", tenant_id="t")
    rq_tasks.run_profile_update({"id": "s-1"}, tenant_id="t")

    assert called == {
        "upload": "u-10",
        "exam": "e-10",
        "profile": {"id": "s-1"},
    }


def test_run_chat_job_requeues_next_job(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    finish_calls: List[Dict[str, str]] = []

    class _Store:
        def finish(self, job_id: str, lane_id: str) -> str | None:
            finish_calls.append({"job_id": job_id, "lane_id": lane_id})
            return "chat-next"

    processed: List[str] = []
    mod = SimpleNamespace(process_chat_job=lambda job_id: processed.append(job_id))

    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: _Store())
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)

    rq_tasks.run_chat_job("chat-1", "lane-1", tenant_id="t")

    assert processed == ["chat-1"]
    assert finish_calls == [{"job_id": "chat-1", "lane_id": "lane-1"}]
    assert len(queue.calls) == 1
    assert queue.calls[0]["func"] is rq_tasks.run_chat_job
    assert queue.calls[0]["args"] == ("chat-next", "lane-1")


def test_run_chat_job_finally_runs_even_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    finish_calls: List[str] = []

    class _Store:
        def finish(self, job_id: str, lane_id: str) -> str | None:
            finish_calls.append(f"{job_id}:{lane_id}")
            return None

    mod = SimpleNamespace(
        process_chat_job=lambda _job_id: (_ for _ in ()).throw(RuntimeError("process failed"))
    )

    monkeypatch.setattr(rq_tasks, "load_tenant_module", lambda tenant_id: mod)
    monkeypatch.setattr(rq_tasks, "_lane_store", lambda _mod, tenant_id: _Store())
    monkeypatch.setattr(rq_tasks, "_get_queue", lambda: queue)

    with pytest.raises(RuntimeError, match="process failed"):
        rq_tasks.run_chat_job("chat-2", "lane-2", tenant_id="t")

    assert finish_calls == ["chat-2:lane-2"]
    assert queue.calls == []
