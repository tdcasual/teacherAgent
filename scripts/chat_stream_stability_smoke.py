#!/usr/bin/env python3
"""
Chat stream stability smoke test.

Focus:
- Event log append/load consistency under concurrent writes.
- Signal registry behavior under capacity pressure and TTL cleanup.

This script is dependency-free and runs against local service modules only.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.api.chat_event_stream_service as stream_service
from services.api.chat_event_stream_service import (
    ChatEventStreamDeps,
    append_chat_event,
    clear_chat_stream_signal,
    load_chat_events_incremental,
    notify_chat_stream_event,
    wait_for_chat_stream_event,
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _build_deps(base_dir: Path) -> ChatEventStreamDeps:
    return ChatEventStreamDeps(
        chat_job_path=lambda job_id: base_dir / "chat_jobs" / str(job_id),
        chat_job_lock=threading.Lock(),
        now_iso=_now_iso,
        notify_job_event=notify_chat_stream_event,
        wait_job_event=wait_for_chat_stream_event,
    )


def _append_job_events(job_id: str, events_per_job: int, deps: ChatEventStreamDeps) -> int:
    total = max(3, int(events_per_job))
    append_chat_event(job_id, "job.queued", {"status": "queued"}, deps=deps)
    append_chat_event(job_id, "job.processing", {"status": "processing"}, deps=deps)
    for idx in range(max(0, total - 3)):
        append_chat_event(job_id, "assistant.delta", {"delta": f"{job_id}:{idx}"}, deps=deps)
    append_chat_event(job_id, "job.done", {"status": "done", "reply": f"ok:{job_id}"}, deps=deps)
    return total


def _count_loaded_events(job_id: str, deps: ChatEventStreamDeps) -> int:
    cursor = 0
    offset = 0
    total = 0
    for _ in range(20):
        batch, offset = load_chat_events_incremental(
            job_id,
            deps=deps,
            after_event_id=cursor,
            offset_hint=offset,
            limit=500,
        )
        if not batch:
            break
        total += len(batch)
        max_id = max(int(item.get("event_id") or 0) for item in batch)
        cursor = max(cursor, max_id)
    return total


def _signal_count() -> int:
    with stream_service._STREAM_SIGNAL_LOCK:
        return len(stream_service._STREAM_SIGNALS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat stream stability smoke test")
    parser.add_argument("--jobs", type=int, default=200, help="number of jobs to generate")
    parser.add_argument("--events-per-job", type=int, default=5, help="events per job (min 3)")
    parser.add_argument("--writers", type=int, default=16, help="parallel workers for event appends")
    parser.add_argument("--signal-cap", type=int, default=256, help="temporary max signal entries for smoke run")
    parser.add_argument("--signal-ttl-sec", type=float, default=0.2, help="temporary signal TTL for smoke run")
    parser.add_argument("--report", default="", help="optional JSON report output path")
    args = parser.parse_args()

    jobs = max(1, int(args.jobs))
    events_per_job = max(3, int(args.events_per_job))
    writers = max(1, int(args.writers))
    cap = max(1, int(args.signal_cap))
    ttl_sec = max(0.01, float(args.signal_ttl_sec))
    effective_ttl_sec = max(1.0, ttl_sec)

    t0 = time.monotonic()
    report: Dict[str, int | float | bool] = {
        "ok": False,
        "jobs": jobs,
        "events_per_job": events_per_job,
        "writers": writers,
        "signal_cap": cap,
        "signal_ttl_sec": ttl_sec,
        "signal_ttl_effective_sec": effective_ttl_sec,
    }

    orig_cap = stream_service.CHAT_STREAM_SIGNAL_MAX_ENTRIES
    orig_ttl = stream_service.CHAT_STREAM_SIGNAL_TTL_SEC
    with stream_service._STREAM_SIGNAL_LOCK:
        stream_service._STREAM_SIGNALS.clear()

    try:
        stream_service.CHAT_STREAM_SIGNAL_MAX_ENTRIES = cap
        stream_service.CHAT_STREAM_SIGNAL_TTL_SEC = ttl_sec

        with tempfile.TemporaryDirectory() as td:
            deps = _build_deps(Path(td))
            job_ids = [f"smoke-job-{idx}" for idx in range(jobs)]

            expected_by_job: Dict[str, int] = {}
            with ThreadPoolExecutor(max_workers=writers) as ex:
                fut_map = {
                    ex.submit(_append_job_events, job_id, events_per_job, deps): job_id
                    for job_id in job_ids
                }
                for fut in as_completed(fut_map):
                    job_id = fut_map[fut]
                    expected_by_job[job_id] = int(fut.result())

            mismatches: List[str] = []
            loaded_total = 0
            for job_id in job_ids:
                loaded = _count_loaded_events(job_id, deps)
                expected = int(expected_by_job.get(job_id) or 0)
                loaded_total += loaded
                if loaded != expected:
                    mismatches.append(job_id)

            signal_entries_after_terminals = _signal_count()

            # Capacity pressure on non-terminal job ids.
            for idx in range(jobs * 3):
                notify_chat_stream_event(f"wave-live-{idx}")
            signal_entries_after_capacity_wave = _signal_count()

            # TTL cleanup trigger.
            time.sleep(effective_ttl_sec + 0.03)
            wait_for_chat_stream_event("ttl-probe", last_seen_version=0, timeout_sec=0.0)
            signal_entries_after_ttl_cleanup = _signal_count()
            clear_chat_stream_signal("ttl-probe")

            report.update(
                {
                    "expected_events_total": jobs * events_per_job,
                    "loaded_events_total": loaded_total,
                    "load_mismatch_jobs": len(mismatches),
                    "signal_entries_after_terminals": signal_entries_after_terminals,
                    "signal_entries_after_capacity_wave": signal_entries_after_capacity_wave,
                    "signal_entries_after_ttl_cleanup": signal_entries_after_ttl_cleanup,
                }
            )

            ok = True
            if mismatches:
                ok = False
                report["error"] = f"event_load_mismatch:{len(mismatches)}"
            elif signal_entries_after_capacity_wave > cap:
                ok = False
                report["error"] = "signal_capacity_exceeded"
            report["ok"] = ok
    finally:
        stream_service.CHAT_STREAM_SIGNAL_MAX_ENTRIES = orig_cap
        stream_service.CHAT_STREAM_SIGNAL_TTL_SEC = orig_ttl

    report["duration_ms"] = int((time.monotonic() - t0) * 1000)
    print(json.dumps(report, ensure_ascii=False))

    report_path = str(args.report or "").strip()
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not bool(report.get("ok")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
