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
    from services.api import app as app_mod

    try:
        app_mod.start_tenant_runtime()
    except RuntimeError as exc:
        assert "rq" in str(exc).lower()
    else:
        assert False, "expected RuntimeError when rq not enabled"
