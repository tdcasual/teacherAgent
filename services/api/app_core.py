from __future__ import annotations

# mypy: disable-error-code=name-defined

import csv
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from collections import deque

_log = logging.getLogger(__name__)


def _reexport_private_symbols(module: Any) -> None:
    """Compatibility shim: expose underscore-prefixed names on app_core facade."""
    for _name, _value in vars(module).items():
        if _name.startswith("_") and not _name.startswith("__"):
            globals().setdefault(_name, _value)

from llm_gateway import LLMGateway
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

from .app_core_service_imports import *  # noqa: F401,F403
try:
    from mem0_config import load_dotenv

    load_dotenv()
except Exception:
    _log.warning("failed to import or run mem0_config.load_dotenv", exc_info=True)
    pass

import importlib as _importlib
from . import config as _config_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_config_module)
from .config import *  # noqa: F401,F403 — re-export all configuration constants
from .config import (
    _TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
    _TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
    _TEACHER_MEMORY_SENSITIVE_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    _settings,
)

from . import paths as _paths_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_paths_module)
from .paths import *  # noqa: F401,F403 — re-export all path resolution functions

from . import job_repository as _job_repository_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_job_repository_module)
from .job_repository import *  # noqa: F401,F403 — re-export all job repository functions
from .job_repository import _atomic_write_json, _try_acquire_lockfile, _release_lockfile

from . import session_store as _session_store_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_session_store_module)
from .session_store import *  # noqa: F401,F403 — re-export all session store functions

from . import chat_lane_repository as _chat_lane_repository_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_chat_lane_repository_module)
from .chat_lane_repository import *  # noqa: F401,F403 — re-export all chat lane repository functions
from .chat_lane_repository import (
    _chat_last_user_text,
    _chat_text_fingerprint,
    _chat_lane_store,
    _chat_lane_load_locked,
    _chat_find_position_locked,
    _chat_enqueue_locked,
    _chat_has_pending_locked,
    _chat_pick_next_locked,
    _chat_mark_done_locked,
    _chat_register_recent_locked,
    _chat_recent_job_locked,
    _chat_request_map_path,
    _chat_request_map_get,
    _chat_request_map_set_if_absent,
)

from . import exam_utils as _exam_utils_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_exam_utils_module)
from .exam_utils import *  # noqa: F401,F403

from . import core_utils as _core_utils_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_core_utils_module)
from .core_utils import *  # noqa: F401,F403

from . import profile_service as _profile_service_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_profile_service_module)
from .profile_service import *  # noqa: F401,F403

from . import assignment_data_service as _assignment_data_service_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_assignment_data_service_module)
from .assignment_data_service import *  # noqa: F401,F403

from . import teacher_memory_core as _teacher_memory_core_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_teacher_memory_core_module)
from .teacher_memory_core import *  # noqa: F401,F403 — re-export all teacher memory functions
_reexport_private_symbols(_teacher_memory_core_module)

def _rq_enabled() -> bool:
    return _rq_enabled_impl()

_reset_runtime_state(sys.modules[__name__], create_chat_idempotency_store=create_chat_idempotency_store)

from .wiring import chat_wiring as _chat_wiring_module
from .wiring import assignment_wiring as _assignment_wiring_module
from .wiring import exam_wiring as _exam_wiring_module
from .wiring import student_wiring as _student_wiring_module
from .wiring import teacher_wiring as _teacher_wiring_module
from .wiring import worker_wiring as _worker_wiring_module
from .wiring import misc_wiring as _misc_wiring_module
from .wiring import skill_wiring as _skill_wiring_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_chat_wiring_module)
    _importlib.reload(_assignment_wiring_module)
    _importlib.reload(_exam_wiring_module)
    _importlib.reload(_student_wiring_module)
    _importlib.reload(_teacher_wiring_module)
    _importlib.reload(_worker_wiring_module)
    _importlib.reload(_misc_wiring_module)
    _importlib.reload(_skill_wiring_module)
from .wiring.chat_wiring import *  # noqa: F401,F403
from .wiring.assignment_wiring import *  # noqa: F401,F403
from .wiring.exam_wiring import *  # noqa: F401,F403
from .wiring.student_wiring import *  # noqa: F401,F403
from .wiring.teacher_wiring import *  # noqa: F401,F403
from .wiring.worker_wiring import *  # noqa: F401,F403
from .wiring.misc_wiring import *  # noqa: F401,F403
from .wiring.skill_wiring import *  # noqa: F401,F403

from . import context_application_facade as _context_application_facade_module
from . import context_runtime_facade as _context_runtime_facade_module
from . import context_io_facade as _context_io_facade_module
if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("DATA_DIR") or os.getenv("UPLOADS_DIR"):
    _importlib.reload(_context_application_facade_module)
    _importlib.reload(_context_runtime_facade_module)
    _importlib.reload(_context_io_facade_module)
from .context_application_facade import *  # noqa: F401,F403
from .context_runtime_facade import *  # noqa: F401,F403
from .context_io_facade import *  # noqa: F401,F403
_reexport_private_symbols(_context_application_facade_module)
_reexport_private_symbols(_context_runtime_facade_module)
_reexport_private_symbols(_context_io_facade_module)
from services.api.chat_limits import (
    acquire_limiters as _acquire_limiters_impl,
    student_inflight_guard as _student_inflight_guard_impl,
    trim_messages as _trim_messages_impl,
)


def _limit(limiter: Any) -> Any:
    return _acquire_limiters_impl(limiter)

def _trim_messages(messages: List[Dict[str, Any]], role_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    return _trim_messages_impl(
        messages,
        role_hint=role_hint,
        max_messages=CHAT_MAX_MESSAGES,
        max_messages_student=CHAT_MAX_MESSAGES_STUDENT,
        max_messages_teacher=CHAT_MAX_MESSAGES_TEACHER,
        max_chars=CHAT_MAX_MESSAGE_CHARS,
    )


def _student_inflight(student_id: Optional[str]) -> Any:
    return _student_inflight_guard_impl(
        student_id=student_id,
        inflight=_STUDENT_INFLIGHT,
        lock=_STUDENT_INFLIGHT_LOCK,
        limit=CHAT_STUDENT_INFLIGHT_LIMIT,
    )

def _setup_diag_logger() -> Optional[logging.Logger]:
    if not DIAG_LOG_ENABLED:
        return None
    DIAG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("diag")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(str(DIAG_LOG_PATH), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


_DIAG_LOGGER = _setup_diag_logger()
LLM_GATEWAY = LLMGateway()

def diag_log(event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    if not DIAG_LOG_ENABLED or _DIAG_LOGGER is None:
        return
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
    }
    if payload:
        record.update(payload)
    try:
        _DIAG_LOGGER.info(json.dumps(record, ensure_ascii=False, default=str))
    except Exception:
        _log.debug("diag_log serialization failed for event=%s", event)
        pass

def chat_job_path(job_id: str) -> Path:
    return _chat_job_path_impl(job_id, deps=_chat_job_repo_deps())

def load_chat_job(job_id: str) -> Dict[str, Any]:
    return _load_chat_job_impl(job_id, deps=_chat_job_repo_deps())

def write_chat_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    return _write_chat_job_impl(job_id, updates, deps=_chat_job_repo_deps(), overwrite=overwrite)

def _chat_job_claim_path(job_id: str) -> Path:
    return chat_job_path(job_id) / "claim.lock"

def _inline_backend_factory():
    upload_deps = upload_worker_deps()
    exam_deps = exam_worker_deps()
    profile_deps = profile_update_worker_deps()
    chat_deps = chat_worker_deps()
    return build_inline_backend(
        enqueue_upload_job_fn=lambda job_id: upload_worker_service.enqueue_upload_job_inline(job_id, deps=upload_deps),
        enqueue_exam_job_fn=lambda job_id: exam_worker_service.enqueue_exam_job_inline(job_id, deps=exam_deps),
        enqueue_profile_update_fn=lambda payload: profile_update_worker_service.enqueue_profile_update_inline(
            payload, deps=profile_deps
        ),
        enqueue_chat_job_fn=lambda job_id, lane_id=None: _enqueue_chat_job_impl(
            job_id, deps=chat_deps, lane_id=lane_id
        ),
        scan_pending_upload_jobs_fn=lambda: upload_worker_service.scan_pending_upload_jobs_inline(deps=upload_deps),
        scan_pending_exam_jobs_fn=lambda: exam_worker_service.scan_pending_exam_jobs_inline(deps=exam_deps),
        scan_pending_chat_jobs_fn=lambda: _scan_pending_chat_jobs_impl(deps=chat_deps),
        start_fn=lambda: start_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=PROFILE_UPDATE_ASYNC,
        ),
        stop_fn=lambda: stop_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=PROFILE_UPDATE_ASYNC,
        ),
    )
