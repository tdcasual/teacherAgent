"""Request ID propagation via ContextVar + logging filter.

Usage:
    - The middleware in app.py sets the request_id for each request.
    - The logging filter attaches request_id to every log record.
    - Response header ``x-request-id`` is added automatically.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


class RequestIdFilter(logging.Filter):
    """Inject ``request_id`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get("")  # type: ignore[attr-defined]
        return True
