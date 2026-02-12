from __future__ import annotations

import os
import threading
import logging
_log = logging.getLogger(__name__)



def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default)) or str(default)).strip()
    try:
        value = int(raw)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        value = int(default)
    return max(1, int(value))


# Global (process-wide) concurrency caps. These are shared across all in-process
# tenant app instances to prevent one tenant from exhausting all resources.
OCR_MAX_CONCURRENCY = _env_int("OCR_MAX_CONCURRENCY", 4)
LLM_MAX_CONCURRENCY = _env_int("LLM_MAX_CONCURRENCY", 8)
LLM_MAX_CONCURRENCY_STUDENT = _env_int("LLM_MAX_CONCURRENCY_STUDENT", LLM_MAX_CONCURRENCY)
LLM_MAX_CONCURRENCY_TEACHER = _env_int("LLM_MAX_CONCURRENCY_TEACHER", LLM_MAX_CONCURRENCY)

GLOBAL_OCR_SEMAPHORE = threading.BoundedSemaphore(OCR_MAX_CONCURRENCY)
GLOBAL_LLM_SEMAPHORE = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY)
GLOBAL_LLM_SEMAPHORE_STUDENT = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY_STUDENT)
GLOBAL_LLM_SEMAPHORE_TEACHER = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY_TEACHER)

CHART_EXEC_MAX_CONCURRENCY = _env_int("CHART_EXEC_MAX_CONCURRENCY", 3)
GLOBAL_CHART_EXEC_SEMAPHORE = threading.BoundedSemaphore(CHART_EXEC_MAX_CONCURRENCY)

