from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ChatApiDeps:
    start_chat: Callable[[Any], Dict[str, Any]]


def start_chat_api(req: Any, *, deps: ChatApiDeps) -> Dict[str, Any]:
    return deps.start_chat(req)
