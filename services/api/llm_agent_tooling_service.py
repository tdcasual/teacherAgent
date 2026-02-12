from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)


def parse_tool_json_safe(content: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(content)
    except Exception:
        _log.debug("unparseable tool JSON content: %.120s", content)
        return None
    return data if isinstance(data, dict) else None
