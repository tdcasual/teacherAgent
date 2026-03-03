from __future__ import annotations

from typing import Any, Iterable, Set

from . import core_service_imports as _core_service_imports_module
from . import core_services_application as _core_services_application_module
from . import core_services_io as _core_services_io_module
from . import core_services_runtime as _core_services_runtime_module

_DELEGATE_MODULES = (
    _core_service_imports_module,
    _core_services_application_module,
    _core_services_runtime_module,
    _core_services_io_module,
)


def _iter_export_names(module: Any) -> Iterable[str]:
    declared = getattr(module, "__all__", None)
    if isinstance(declared, (list, tuple, set)):
        for item in declared:
            name = str(item or "").strip()
            if name and not name.startswith("_"):
                yield name
        return
    for item in vars(module).keys():
        name = str(item or "").strip()
        if name and not name.startswith("_"):
            yield name


def _bind_delegate_exports() -> Set[str]:
    exported: Set[str] = set()
    for module in _DELEGATE_MODULES:
        for name in _iter_export_names(module):
            if name in globals():
                exported.add(name)
                continue
            try:
                globals()[name] = getattr(module, name)
                exported.add(name)
            except AttributeError:
                continue
    return exported


__all__ = sorted(_bind_delegate_exports())
