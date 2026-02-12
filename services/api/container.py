from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AppContainer:
    core: Any


def build_app_container(*, core: Any) -> AppContainer:
    return AppContainer(core=core)
