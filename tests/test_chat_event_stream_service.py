from __future__ import annotations

import json
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import services.api.chat_event_stream_service as stream_service
from services.api.chat_event_stream_service import (
    ChatEventStreamDeps,
    append_chat_event,
    chat_event_log_path,
    clear_chat_stream_signal,
    encode_sse_event,
    load_chat_events,
    load_chat_events_incremental,
    notify_chat_stream_event,
    wait_for_chat_stream_event,
)


def _deps(tmp_root: Path) -> ChatEventStreamDeps:
    return ChatEventStreamDeps(
        chat_job_path=lambda job_id: tmp_root / "chat_jobs" / str(job_id),
        chat_job_lock=threading.Lock(),
        now_iso=lambda: "2026-02-15T12:00:00",
    )


def test_append_and_load_chat_events_ordered() -> None:
    with TemporaryDirectory() as td:
        deps = _deps(Path(td))
        first = append_chat_event("job-1", "job.queued", {"status": "queued"}, deps=deps)
        second = append_chat_event("job-1", "tool.start", {"tool_name": "exam.get"}, deps=deps)
        assert int(first["event_id"]) == 1
        assert int(second["event_id"]) == 2
        assert int(first.get("event_version") or 0) == 1
        assert int(second.get("event_version") or 0) == 1

        items = load_chat_events("job-1", deps=deps, after_event_id=1, limit=20)
        assert len(items) == 1
        assert items[0].get("type") == "tool.start"
        assert (items[0].get("payload") or {}).get("tool_name") == "exam.get"


def test_encode_sse_event_payload_shape() -> None:
    event = {"event_id": 3, "type": "assistant.delta", "payload": {"delta": "abc"}}
    sse = encode_sse_event(event)
    assert "id: 3" in sse
    assert "event: assistant.delta" in sse
    lines = [line for line in sse.splitlines() if line.startswith("data:")]
    assert len(lines) == 1
    envelope = json.loads(lines[0][5:].strip())
    assert envelope["event_version"] == 1
    assert envelope["event_id"] == 3
    assert envelope["type"] == "assistant.delta"
    assert envelope["payload"]["delta"] == "abc"


def test_load_chat_events_handles_missing_log() -> None:
    with TemporaryDirectory() as td:
        deps = _deps(Path(td))
        assert load_chat_events("missing-job", deps=deps) == []
        assert not chat_event_log_path("missing-job", deps=deps).exists()


def test_load_chat_events_incremental_reuses_offset_hint() -> None:
    with TemporaryDirectory() as td:
        deps = _deps(Path(td))
        append_chat_event("job-inc-1", "job.queued", {"status": "queued"}, deps=deps)
        append_chat_event("job-inc-1", "assistant.delta", {"delta": "A"}, deps=deps)

        first_batch, first_offset = load_chat_events_incremental("job-inc-1", deps=deps, after_event_id=0)
        assert [int(item.get("event_id") or 0) for item in first_batch] == [1, 2]
        assert first_offset > 0

        append_chat_event("job-inc-1", "assistant.delta", {"delta": "B"}, deps=deps)
        second_batch, second_offset = load_chat_events_incremental(
            "job-inc-1",
            deps=deps,
            after_event_id=2,
            offset_hint=first_offset,
        )
        assert [int(item.get("event_id") or 0) for item in second_batch] == [3]
        assert second_offset >= first_offset


def test_load_chat_events_incremental_falls_back_when_offset_hint_out_of_range() -> None:
    with TemporaryDirectory() as td:
        deps = _deps(Path(td))
        append_chat_event("job-inc-2", "job.queued", {"status": "queued"}, deps=deps)
        append_chat_event("job-inc-2", "job.processing", {"status": "processing"}, deps=deps)

        batch, offset = load_chat_events_incremental(
            "job-inc-2",
            deps=deps,
            after_event_id=0,
            offset_hint=10_000,
        )
        assert [int(item.get("event_id") or 0) for item in batch] == [1, 2]
        assert offset > 0


def test_chat_stream_signal_notify_and_wait_progresses_version() -> None:
    job_id = "signal-job-1"
    base = wait_for_chat_stream_event(job_id, last_seen_version=0, timeout_sec=0.0)
    notify_chat_stream_event(job_id)
    after_notify = wait_for_chat_stream_event(job_id, last_seen_version=base, timeout_sec=0.0)
    assert after_notify > base

    no_change = wait_for_chat_stream_event(job_id, last_seen_version=after_notify, timeout_sec=0.0)
    assert no_change == after_notify


def test_chat_stream_signal_clear_resets_signal_state() -> None:
    job_id = "signal-job-clear-1"
    base = wait_for_chat_stream_event(job_id, last_seen_version=0, timeout_sec=0.0)
    notify_chat_stream_event(job_id)
    after_notify = wait_for_chat_stream_event(job_id, last_seen_version=base, timeout_sec=0.0)
    assert after_notify > base

    clear_chat_stream_signal(job_id)
    reset = wait_for_chat_stream_event(job_id, last_seen_version=after_notify, timeout_sec=0.0)
    assert reset == 0


def test_chat_stream_signal_registry_evicts_when_over_capacity(monkeypatch) -> None:
    with stream_service._STREAM_SIGNAL_LOCK:
        stream_service._STREAM_SIGNALS.clear()
        stream_service._STREAM_SIGNAL_LAST_SWEEP_TS = 0.0
    monkeypatch.setattr(stream_service, "CHAT_STREAM_SIGNAL_MAX_ENTRIES", 3)
    monkeypatch.setattr(stream_service, "CHAT_STREAM_SIGNAL_TTL_SEC", 3600.0)

    for idx in range(6):
        notify_chat_stream_event(f"signal-cap-{idx}")

    with stream_service._STREAM_SIGNAL_LOCK:
        assert len(stream_service._STREAM_SIGNALS) <= 3


def test_chat_stream_signal_registry_keeps_recently_touched_entries(monkeypatch) -> None:
    with stream_service._STREAM_SIGNAL_LOCK:
        stream_service._STREAM_SIGNALS.clear()
        stream_service._STREAM_SIGNAL_LAST_SWEEP_TS = 0.0
    monkeypatch.setattr(stream_service, "CHAT_STREAM_SIGNAL_MAX_ENTRIES", 3)
    monkeypatch.setattr(stream_service, "CHAT_STREAM_SIGNAL_TTL_SEC", 3600.0)

    notify_chat_stream_event("signal-lru-a")
    notify_chat_stream_event("signal-lru-b")
    notify_chat_stream_event("signal-lru-c")
    # Touch A again so B becomes the oldest entry.
    notify_chat_stream_event("signal-lru-a")
    notify_chat_stream_event("signal-lru-d")

    with stream_service._STREAM_SIGNAL_LOCK:
        keys = set(stream_service._STREAM_SIGNALS.keys())
    assert "signal-lru-a" in keys
    assert "signal-lru-c" in keys
    assert "signal-lru-d" in keys
    assert "signal-lru-b" not in keys


def test_chat_stream_signal_evict_is_not_run_on_every_notify(monkeypatch) -> None:
    calls = 0
    original = stream_service._evict_stream_signals_locked

    def _counting_evict(now: float) -> None:
        nonlocal calls
        calls += 1
        original(now)

    with stream_service._STREAM_SIGNAL_LOCK:
        stream_service._STREAM_SIGNALS.clear()
        stream_service._STREAM_SIGNAL_LAST_SWEEP_TS = 0.0
    monkeypatch.setattr(stream_service, "_evict_stream_signals_locked", _counting_evict)
    monkeypatch.setattr(stream_service, "CHAT_STREAM_SIGNAL_MAX_ENTRIES", 1024)
    monkeypatch.setattr(stream_service, "CHAT_STREAM_SIGNAL_TTL_SEC", 3600.0)

    for idx in range(20):
        notify_chat_stream_event(f"signal-hot-{idx}")

    # Hot path should amortize eviction work instead of scanning/sorting every call.
    assert calls < 20
