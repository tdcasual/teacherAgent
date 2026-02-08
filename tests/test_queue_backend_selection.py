def test_selects_rq_backend(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    from services.api.queue_backend import get_queue_backend

    backend = get_queue_backend()
    assert backend.name == "rq"


def test_rq_required_when_no_inline_backend(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    from services.api import queue_backend

    try:
        queue_backend.get_queue_backend(tenant_id=None, inline_backend=None)
    except RuntimeError as exc:
        assert "rq" in str(exc).lower()
    else:
        assert False, "expected RuntimeError when rq not enabled"
