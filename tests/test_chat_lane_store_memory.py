def test_memory_lane_store_enqueue_and_finish():
    from services.api.chat_lane_store import MemoryLaneStore

    store = MemoryLaneStore()
    info, dispatch = store.enqueue("job1", "lane1")
    assert dispatch is True
    assert info["lane_queue_position"] == 0


def test_chat_lane_load_uses_store_even_when_rq_disabled(monkeypatch):
    from services.api import app as app_mod
    from services.api import chat_lane_repository as _chat_lane_repo

    called = {"lane_load": 0}

    class FakeStore:
        def lane_load(self, lane_id: str):
            called["lane_load"] += 1
            return {"queued": 0, "active": 0, "total": 0}

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(app_mod, "_rq_enabled", lambda: False)
    monkeypatch.setattr(_chat_lane_repo, "_chat_lane_store", lambda: FakeStore())

    result = app_mod._chat_lane_load_locked("lane1")
    assert called["lane_load"] == 1
    assert result["total"] == 0
