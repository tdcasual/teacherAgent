from __future__ import annotations

import threading
import types

from services.api.wiring import CURRENT_CORE, chat_wiring


def test_chat_worker_thread_factory_sets_current_core(monkeypatch, tmp_path):
    fake_core = types.SimpleNamespace(
        CHAT_JOB_DIR=tmp_path / "jobs",
        CHAT_JOB_LOCK=threading.Lock(),
        CHAT_JOB_EVENT=threading.Event(),
        CHAT_WORKER_STOP_EVENT=threading.Event(),
        CHAT_WORKER_THREADS=[],
        CHAT_WORKER_POOL_SIZE=1,
        CHAT_JOB_WORKER_STARTED=False,
        load_chat_job=lambda _job_id: {},
        write_chat_job=lambda _job_id, _updates: {},
        process_chat_job=lambda _job_id: None,
        diag_log=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(chat_wiring, "_app_core", lambda _core=None: fake_core)

    previous_core = CURRENT_CORE.get(None)
    deps = chat_wiring._chat_worker_deps()

    captured = {"core": None}
    done = threading.Event()

    def _target():
        captured["core"] = CURRENT_CORE.get(None)
        done.set()

    worker = deps.thread_factory(target=_target, daemon=True, name="test-chat-worker-context")
    worker.start()
    worker.join(1.0)

    assert done.is_set() is True
    assert captured["core"] is fake_core
    assert CURRENT_CORE.get(None) is previous_core
