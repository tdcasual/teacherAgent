def test_selects_rq_backend(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    from services.api.queue.queue_backend import get_queue_backend

    backend = get_queue_backend()
    assert backend.name == "rq"


def test_rq_required_when_no_inline_backend(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    from services.api.queue import queue_backend

    try:
        queue_backend.get_queue_backend(tenant_id=None)
    except RuntimeError as exc:
        assert "rq" in str(exc).lower()
    else:
        assert False, "expected RuntimeError when rq not enabled"


def test_inline_backend_removed(monkeypatch):
    import importlib

    try:
        importlib.import_module("services.api.queue_backend_inline")
    except ModuleNotFoundError:
        assert True
    else:
        assert False, "queue_backend_inline should be removed"
