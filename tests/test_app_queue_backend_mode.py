import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from services.api.queue.queue_backend import rq_enabled
from tests.helpers.app_factory import create_test_app


def test_app_registers_routes():
    with TemporaryDirectory() as td:
        app_mod = create_test_app(Path(td))
        paths = {route.path for route in app_mod.app.router.routes}
        assert "/health" in paths


def test_rq_mode_disables_inprocess_workers(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    assert rq_enabled() is True


def test_runtime_start_uses_runtime_manager_when_not_pytest(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    calls = []

    def _fake_start(*, deps):
        calls.append(deps)
    with TemporaryDirectory() as td:
        app_mod = create_test_app(
            Path(td),
            env_unset=("PYTEST_CURRENT_TEST", "JOB_QUEUE_BACKEND", "RQ_BACKEND_ENABLED"),
        )
        from services.api.runtime import bootstrap

        monkeypatch.setattr(bootstrap, "start_tenant_runtime", _fake_start)
        bootstrap.start_runtime(app_mod=app_mod.app)
    assert calls
    assert calls[0].is_pytest is False


def test_lifespan_does_not_start_workers(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "rq")
    monkeypatch.setenv("RQ_BACKEND_ENABLED", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    import sys
    import types

    stub = types.ModuleType("services.api.workers.rq_tasks")
    stub.require_redis = lambda: None
    monkeypatch.setitem(sys.modules, "services.api.workers.rq_tasks", stub)

    called = {"start": 0}

    def fake_start():
        called["start"] += 1

    import asyncio

    async def run():
        with TemporaryDirectory() as td:
            app_mod = create_test_app(
                Path(td),
                env_overrides={"JOB_QUEUE_BACKEND": "rq", "RQ_BACKEND_ENABLED": "1"},
                env_unset=("PYTEST_CURRENT_TEST",),
            )
            from services.api.runtime import bootstrap, lifecycle

            monkeypatch.setattr(bootstrap, "start_inline_workers", fake_start, raising=False)
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
