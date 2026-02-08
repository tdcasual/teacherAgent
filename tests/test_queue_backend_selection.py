def test_selects_rq_backend(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    from services.api.queue_backend import get_queue_backend

    backend = get_queue_backend()
    assert backend.name == "rq"
