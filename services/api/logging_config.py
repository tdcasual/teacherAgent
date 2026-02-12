"""Structured logging configuration.

Environment variables:
    LOG_FORMAT  – "json" for JSON lines, "text" for human-readable (default: "text")
    LOG_LEVEL   – root log level name (default: "INFO")
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        # Attach request_id if present (set by request_context middleware)
        rid = getattr(record, "request_id", None)
        if rid:
            payload["request_id"] = rid
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure root logger based on LOG_FORMAT and LOG_LEVEL env vars."""
    fmt = os.getenv("LOG_FORMAT", "text").strip().lower()
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates on reload
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s"))
    root.addHandler(handler)
