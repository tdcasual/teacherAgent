from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerStopResult:
    worker_started: bool
    clear_thread_ref: bool


def compute_stop_result(*, thread_alive: bool) -> WorkerStopResult:
    is_alive = bool(thread_alive)
    return WorkerStopResult(
        worker_started=is_alive,
        clear_thread_ref=not is_alive,
    )
