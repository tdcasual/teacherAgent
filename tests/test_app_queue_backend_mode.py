import pytest
from services.api.queue.queue_backend import rq_enabled


def test_app_registers_routes():
    import importlib

    import services.api.app as app_mod

    importlib.reload(app_mod)
    app_obj = getattr(app_mod, "_DEFAULT_APP", app_mod.app)
    paths = {route.path for route in app_obj.router.routes}
    assert "/health" in paths


def test_rq_mode_disables_inprocess_workers(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    assert rq_enabled() is True


def test_runtime_start_requires_explicit_queue_mode_when_not_pytest(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    from services.api.runtime import bootstrap

    with pytest.raises(RuntimeError, match="RQ backend required"):
        bootstrap.start_runtime()


def test_lifespan_does_not_start_workers(monkeypatch):
    from services.api import app as app_mod
    from services.api.runtime import bootstrap, lifecycle

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

    monkeypatch.setattr(bootstrap, "start_inline_workers", fake_start, raising=False)

    import asyncio

    async def run():
        async with lifecycle.app_lifespan(app_mod.app):
            pass

    asyncio.run(run())
    assert called["start"] == 0


def test_bootstrap_runtime_prefers_sys_modules_app_when_package_attr_is_stale(monkeypatch):
    import sys
    import types

    import services.api as api_pkg
    from services.api.runtime import bootstrap

    stale_app = types.ModuleType("services.api.app")
    stale_app.TENANT_ID = "stale"  # type: ignore[attr-defined]
    fresh_app = types.ModuleType("services.api._app_fresh")
    fresh_app.TENANT_ID = "fresh"  # type: ignore[attr-defined]

    calls = []

    def _fake_start(*, deps):
        calls.append(("start", deps.tenant_id))

    def _fake_stop(*, deps):
        calls.append(("stop", deps.tenant_id))

    monkeypatch.setattr(bootstrap, "start_tenant_runtime", _fake_start)
    monkeypatch.setattr(bootstrap, "stop_tenant_runtime", _fake_stop)
    monkeypatch.setitem(sys.modules, "services.api.app", fresh_app)
    monkeypatch.setattr(api_pkg, "app", stale_app, raising=False)

    bootstrap.start_runtime()
    bootstrap.stop_runtime()

    assert calls == [("start", "fresh"), ("stop", "fresh")]
