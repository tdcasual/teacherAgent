from __future__ import annotations

import json
from typing import Any, Dict, Optional


def parse_tool_json_safe(content: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(content)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
