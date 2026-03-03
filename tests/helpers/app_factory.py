from __future__ import annotations

import os
import sys
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class TestAppModule:
    app: Any
    _core: Any

    def get_core(self) -> Any:
        return self._core


def _purge_services_api_modules() -> None:
    config_mod = sys.modules.get("services.api.config")
    if config_mod is not None and hasattr(config_mod, "reset_default_config"):
        config_mod.reset_default_config()
    module_order = (
        "services.api.config",
        "services.api.teacher_memory_apply_service",
        "services.api.teacher_memory_propose_service",
        "services.api.teacher_memory_auto_service",
        "services.api.teacher_session_compaction_helpers",
        "services.api.teacher_session_compaction_service",
        "services.api.teacher_memory_deps",
        "services.api.teacher_memory_core",
        "services.api.paths",
        "services.api.job_repository",
        "services.api.session_store",
        "services.api.app_core",
        "services.api.app",
    )
    for name in module_order:
        mod = sys.modules.get(name)
        if mod is not None:
            importlib.reload(mod)


def create_test_app(
    tmp_dir: Path,
    *,
    env_overrides: Mapping[str, str] | None = None,
    env_unset: Iterable[str] = (),
    use_runtime_entrypoint: bool = False,
    reload_module: bool = False,
    reset_modules: bool = False,
) -> TestAppModule:
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["JOB_QUEUE_BACKEND"] = "inline"
    os.environ["RQ_BACKEND_ENABLED"] = "0"
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("RQ_QUEUE_NAME", None)

    for key in env_unset:
        os.environ.pop(str(key), None)

    if env_overrides:
        for key, value in env_overrides.items():
            os.environ[str(key)] = str(value)

    if reset_modules:
        _purge_services_api_modules()

    import services.api.app as app_mod
    if reload_module:
        app_mod = importlib.reload(app_mod)

    if use_runtime_entrypoint:
        app = app_mod._build_runtime_entrypoint()
    else:
        app = app_mod.create_app(app_mod.load_settings())
    return TestAppModule(app=app, _core=app_mod.get_core(app))
