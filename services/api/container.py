from __future__ import annotations

from dataclasses import dataclass

from .core_runtime import CoreRuntime


@dataclass(frozen=True)
class AppContainer:
    core: CoreRuntime


def build_app_container(*, core: CoreRuntime) -> AppContainer:
    return AppContainer(core=core)
