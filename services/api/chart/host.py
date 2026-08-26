from __future__ import annotations

from typing import Any


def host_call(name: str, *args: Any, **kwargs: Any) -> Any:
    # Tests monkeypatch these names on chart_executor; honor that binding.
    from .. import chart_executor as host

    return getattr(host, name)(*args, **kwargs)
