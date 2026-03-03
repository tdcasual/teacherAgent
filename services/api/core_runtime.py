from __future__ import annotations

import functools
import importlib
import inspect
import types
from typing import Any, Callable

from .config import ConfigValues, build_config
from .runtime.runtime_state import reset_runtime_state
from .runtime_settings import AppSettings, load_settings
from .wiring import CURRENT_CORE


class _SettingsView:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def is_pytest(self) -> bool:
        return bool(self._settings.is_pytest)


class CoreRuntime:
    def __init__(
        self,
        *,
        module: types.ModuleType,
        settings: AppSettings,
        config: ConfigValues,
    ) -> None:
        self._module = module
        self._settings_data = settings
        self._config = config

        for name in ConfigValues.__dataclass_fields__.keys():
            setattr(self, name, getattr(config, name))
        self._settings = _SettingsView(settings)

        # Instance-scoped mutable runtime fields.
        reset_runtime_state(
            self,
            create_chat_idempotency_store=module._core_service_imports_module.create_chat_idempotency_store,
        )

    @property
    def settings(self) -> AppSettings:
        return self._settings_data

    def _wrap_callable(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        inject_core = "core" in inspect.signature(fn).parameters

        @functools.wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            if inject_core and "core" not in kwargs:
                kwargs["core"] = self
            token = CURRENT_CORE.set(self)
            try:
                return fn(*args, **kwargs)
            finally:
                CURRENT_CORE.reset(token)

        return _wrapped

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._module, name)
        if callable(value):
            return self._wrap_callable(value)
        return value


def build_core_runtime(
    *,
    settings: AppSettings | None = None,
    module: types.ModuleType | None = None,
) -> CoreRuntime:
    effective_settings = settings or load_settings()
    app_core_module = module or importlib.import_module("services.api.app_core")
    config = build_config(effective_settings)
    return CoreRuntime(module=app_core_module, settings=effective_settings, config=config)
