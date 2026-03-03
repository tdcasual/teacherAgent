from __future__ import annotations


def test_stop_keeps_started_true_when_thread_alive() -> None:
    from services.api.workers.lifecycle_state import compute_stop_result

    result = compute_stop_result(thread_alive=True)
    assert result.worker_started is True
    assert result.clear_thread_ref is False
