from __future__ import annotations

from services.api.chat_lane_store import MemoryLaneStore


def test_lane_load_and_position_defaults() -> None:
    store = MemoryLaneStore()
    assert store.lane_load("lane-1") == {"queued": 0, "active": 0, "total": 0}
    assert store.find_position("lane-1", "job-x") == 0

    store.enqueue("job-1", "lane-1")
    store.enqueue("job-2", "lane-1")
    assert store.find_position("lane-1", "missing-job") == 0


def test_enqueue_active_and_duplicate_paths() -> None:
    store = MemoryLaneStore()

    first, dispatch_first = store.enqueue("job-1", "lane-1")
    assert dispatch_first is True
    assert first == {"lane_queue_position": 0, "lane_queue_size": 0, "lane_active": True}

    second, dispatch_second = store.enqueue("job-2", "lane-1")
    assert dispatch_second is False
    assert second["lane_queue_position"] == 1
    assert second["lane_queue_size"] == 1
    assert second["lane_active"] is True

    # duplicate queued job hits _queued branch
    dup, dispatch_dup = store.enqueue("job-2", "lane-1")
    assert dispatch_dup is False
    assert dup["lane_queue_position"] == 1
    assert dup["lane_queue_size"] == 1
    assert dup["lane_active"] is True


def test_finish_paths_with_mismatch_and_next_job() -> None:
    store = MemoryLaneStore()

    store.enqueue("job-1", "lane-1")
    store.enqueue("job-2", "lane-1")

    # active mismatch should no-op and return None
    assert store.finish("wrong-job", "lane-1") is None

    # finishing active job promotes next queued job
    assert store.finish("job-1", "lane-1") == "job-2"

    # finishing promoted job empties lane
    assert store.finish("job-2", "lane-1") is None
    assert store.lane_load("lane-1") == {"queued": 0, "active": 0, "total": 0}


def test_finish_empty_lane_and_discard_nonexistent_job() -> None:
    store = MemoryLaneStore()
    assert store.finish("job-x", "lane-x") is None


def test_recent_job_debounce_paths(monkeypatch) -> None:
    # debounce disabled
    disabled = MemoryLaneStore(debounce_ms=0)
    disabled.register_recent("lane-1", "fp", "job-1")
    assert disabled.recent_job("lane-1", "fp") is None

    # debounce enabled
    now = {"value": 1000.0}
    monkeypatch.setattr("services.api.chat_lane_store.time.time", lambda: now["value"])

    store = MemoryLaneStore(debounce_ms=500)
    # debounce enabled but no recent entry
    assert store.recent_job("lane-empty", "fp-0") is None

    store.register_recent("lane-1", "fp-1", "job-1")
    assert store.recent_job("lane-1", "fp-1") == "job-1"

    # mismatch fingerprint
    assert store.recent_job("lane-1", "fp-2") is None

    # expired
    now["value"] = 1001.0
    assert store.recent_job("lane-1", "fp-1") is None
