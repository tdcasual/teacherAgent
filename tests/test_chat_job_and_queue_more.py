from __future__ import annotations

from collections import deque
from pathlib import Path

from services.api import chat_job_repository as cjr
from services.api import chat_queue_service as cqs


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(payload), encoding="utf-8")


def _deps(tmp_path: Path) -> cjr.ChatJobRepositoryDeps:
    return cjr.ChatJobRepositoryDeps(
        chat_job_dir=tmp_path,
        atomic_write_json=_write_json,
        now_iso=lambda: "2026-02-12T00:00:00",
    )


def test_chat_job_exists_handles_unexpected_exceptions(monkeypatch, tmp_path: Path) -> None:
    deps = _deps(tmp_path)

    def _raise_chat_job_path(_job_id: str, _deps: cjr.ChatJobRepositoryDeps):
        raise RuntimeError("path failed")

    monkeypatch.setattr(cjr, "chat_job_path", _raise_chat_job_path)
    assert cjr.chat_job_exists("job-1", deps) is False


def test_write_chat_job_handles_corrupt_existing_json(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    job_dir = cjr.chat_job_path("job-1", deps)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.json").write_text("{bad-json", encoding="utf-8")

    out = cjr.write_chat_job("job-1", {"status": "queued"}, deps, overwrite=False)

    assert out["status"] == "queued"
    assert out["updated_at"] == "2026-02-12T00:00:00"


def test_chat_find_position_returns_zero_for_missing_queue_and_not_found() -> None:
    lanes = {"lane-a": deque(["job-1"])}

    assert cqs.chat_find_position(lanes, "lane-missing", "job-1") == 0
    assert cqs.chat_find_position(lanes, "lane-a", "job-x") == 0


def test_chat_pick_next_returns_empty_when_no_available_lanes() -> None:
    out = cqs.chat_pick_next({}, set(), set(), {}, lane_cursor=3)
    assert out == ("", "", 3)


def test_chat_pick_next_returns_empty_when_all_lanes_active() -> None:
    lanes = {"lane-a": deque(["job-1"])}
    out = cqs.chat_pick_next(
        lanes,
        active_lanes={"lane-a"},
        queued_jobs={"job-1"},
        job_to_lane={"job-1": "lane-a"},
        lane_cursor=0,
    )
    assert out == ("", "", 0)


def test_chat_pick_next_handles_queue_disappearing_after_snapshot() -> None:
    class _Lanes(dict):
        def items(self):
            return [("lane-a", deque(["job-1"]))]

        def get(self, key, default=None):
            assert key == "lane-a"
            return deque()

    out = cqs.chat_pick_next(
        _Lanes(),
        active_lanes=set(),
        queued_jobs={"job-1"},
        job_to_lane={"job-1": "lane-a"},
        lane_cursor=0,
    )
    assert out == ("", "", 0)


def test_chat_recent_job_handles_debounce_disabled_and_missing_lane() -> None:
    assert cqs.chat_recent_job({}, "lane-a", "fp", debounce_ms=0, now_ts=1.0) is None
    assert cqs.chat_recent_job({}, "lane-a", "fp", debounce_ms=100, now_ts=1.0) is None
