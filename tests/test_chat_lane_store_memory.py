def test_memory_lane_store_enqueue_and_finish():
    from services.api.chat_lane_store import MemoryLaneStore

    store = MemoryLaneStore()
    info, dispatch = store.enqueue("job1", "lane1")
    assert dispatch is True
    assert info["lane_queue_position"] == 0
