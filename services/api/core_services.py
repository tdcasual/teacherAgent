from __future__ import annotations

import importlib as _importlib
import os
from typing import Any

from . import core_service_imports as _core_service_imports_module
from . import core_services_application as _core_services_application_module
from . import core_services_io as _core_services_io_module
from . import core_services_runtime as _core_services_runtime_module


def _reexport_public(module: Any) -> None:
    export_names = getattr(module, "__all__", None)
    if export_names is None:
        export_names = [name for name in dir(module) if not name.startswith("_")]
    for name in export_names:
        globals()[name] = getattr(module, name)


if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_core_service_imports_module)
    _importlib.reload(_core_services_application_module)
    _importlib.reload(_core_services_runtime_module)
    _importlib.reload(_core_services_io_module)

_reexport_public(_core_service_imports_module)
_reexport_public(_core_services_application_module)
_reexport_public(_core_services_runtime_module)
_reexport_public(_core_services_io_module)

_INTERNAL_EXPORTS = {
    "_importlib",
    "_reexport_public",
    "_core_service_imports_module",
    "_core_services_application_module",
    "_core_services_runtime_module",
    "_core_services_io_module",
    "_INTERNAL_EXPORTS",
    "Any",
    "os",
}
__all__ = [
    name
    for name in globals()
    if not name.startswith("__") and name not in _INTERNAL_EXPORTS
]
