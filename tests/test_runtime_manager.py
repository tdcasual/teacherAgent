from services.api.runtime.runtime_manager import RuntimeManagerDeps, start_tenant_runtime, stop_tenant_runtime


def test_start_and_stop_runtime_wire_backend_and_validate():
    calls = {}

    def validate_master_key_policy(*, getenv):
        calls["validated"] = True

    def inline_backend_factory():
        return "inline-backend"

    def get_backend(**kwargs):
        calls["backend_args"] = kwargs
        return "backend"

    def start_runtime(*, backend, is_pytest):
        calls["start"] = (backend, is_pytest)

    def stop_runtime(*, backend):
        calls["stop"] = backend

    deps = RuntimeManagerDeps(
        tenant_id="t1",
        is_pytest=True,
        validate_master_key_policy=validate_master_key_policy,
        inline_backend_factory=inline_backend_factory,
        get_backend=get_backend,
        start_runtime=start_runtime,
        stop_runtime=stop_runtime,
    )

    start_tenant_runtime(deps=deps)
    stop_tenant_runtime(deps=deps)

    assert calls["validated"] is True
    assert calls["backend_args"]["tenant_id"] == "t1"
    assert calls["backend_args"]["is_pytest"] is True
    assert calls["start"] == ("backend", True)
    assert calls["stop"] == "backend"
