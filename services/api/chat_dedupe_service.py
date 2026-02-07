from __future__ import annotations

import hashlib
import re
from typing import Any


def chat_last_user_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role") or "") != "user":
            continue
        return str(msg.get("content") or "")
    return ""


def chat_text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()
