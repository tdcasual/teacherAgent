def test_app_registers_routes():
    import importlib

    import services.api.app as app_mod

    importlib.reload(app_mod)
    app_obj = getattr(app_mod, "_DEFAULT_APP", app_mod.app)
    paths = {route.path for route in app_obj.router.routes}
    assert "/health" in paths


def test_rq_mode_disables_inprocess_workers(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    import importlib

    import services.api.app as app_mod

    importlib.reload(app_mod)
    assert app_mod._rq_enabled() is True


def test_rq_required_in_api_startup(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    from services.api import app as app_mod

    try:
        app_mod.start_tenant_runtime()
    except RuntimeError as exc:
        assert "rq" in str(exc).lower()
    else:
        assert False, "expected RuntimeError when rq not enabled"


def test_lifespan_does_not_start_workers(monkeypatch):
    from services.api import app as app_mod

    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    import sys
    import types

    stub = types.ModuleType("services.api.workers.rq_tasks")
    stub.require_redis = lambda: None
    monkeypatch.setitem(sys.modules, "services.api.workers.rq_tasks", stub)

    called = {"start": 0}

    def fake_start():
        called["start"] += 1

    monkeypatch.setattr(app_mod, "_start_inline_workers", fake_start, raising=False)

    import asyncio

    async def run():
        async with app_mod._app_lifespan(app_mod.app):
            pass

    asyncio.run(run())
    assert called["start"] == 0
