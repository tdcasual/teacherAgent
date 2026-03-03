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


from llm_gateway import LLMGateway
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

try:
    from mem0_config import load_dotenv

    load_dotenv()
except Exception:
    _log.warning("failed to import or run mem0_config.load_dotenv", exc_info=True)
    pass

from . import core_services as _core_services_module
from . import core_service_imports as _core_service_imports_module

from . import config as _config_module
from .config import (
    CHAT_JOB_DIR,
    LLM_MAX_CONCURRENCY,
    LLM_MAX_CONCURRENCY_STUDENT,
    LLM_MAX_CONCURRENCY_TEACHER,
    OCR_MAX_CONCURRENCY,
    _TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
    _TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
    _TEACHER_MEMORY_SENSITIVE_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    _settings,
)

from . import paths as _paths_module

from . import job_repository as _job_repository_module
from .job_repository import _atomic_write_json, _try_acquire_lockfile, _release_lockfile

from . import session_store as _session_store_module

from . import chat_lane_repository as _chat_lane_repository_module
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

from . import core_utils as _core_utils_module

from . import profile_service as _profile_service_module

from . import assignment_data_service as _assignment_data_service_module

from . import teacher_memory_core as _teacher_memory_core_module

def _rq_enabled() -> bool:
    return _core_service_imports_module._rq_enabled_impl()

_core_service_imports_module._reset_runtime_state(
    sys.modules[__name__],
    create_chat_idempotency_store=_core_service_imports_module.create_chat_idempotency_store,
)

from .wiring import chat_wiring as _chat_wiring_module
from .wiring import assignment_wiring as _assignment_wiring_module
from .wiring import exam_wiring as _exam_wiring_module
from .wiring import student_wiring as _student_wiring_module
from .wiring import teacher_wiring as _teacher_wiring_module
from .wiring import worker_wiring as _worker_wiring_module
from .wiring import misc_wiring as _misc_wiring_module
from .wiring import skill_wiring as _skill_wiring_module
from . import app_core_wiring_exports as _app_core_wiring_exports_module
from . import app_core_init as _app_core_init_module
from .wiring import CURRENT_CORE

_DELEGATE_MODULES: Tuple[Any, ...] = (
    _core_services_module,
    _config_module,
    _paths_module,
    _job_repository_module,
    _session_store_module,
    _chat_lane_repository_module,
    _exam_utils_module,
    _core_utils_module,
    _profile_service_module,
    _assignment_data_service_module,
    _teacher_memory_core_module,
    _app_core_wiring_exports_module,
)


def _iter_delegate_export_names(module: Any) -> Iterable[str]:
    declared = getattr(module, "__all__", None)
    if isinstance(declared, (list, tuple, set)):
        for item in declared:
            name = str(item or "").strip()
            if name and not name.startswith("_"):
                yield name
        return
    for item in vars(module).keys():
        name = str(item or "").strip()
        if name and not name.startswith("_"):
            yield name


def _bind_delegate_exports() -> None:
    for module in _DELEGATE_MODULES:
        for name in _iter_delegate_export_names(module):
            if name in globals():
                continue
            try:
                globals()[name] = getattr(module, name)
            except AttributeError:
                continue


_bind_delegate_exports()


if CURRENT_CORE.get(None) is None:
    CURRENT_CORE.set(sys.modules[__name__])

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
        max_messages=_config_module.CHAT_MAX_MESSAGES,
        max_messages_student=_config_module.CHAT_MAX_MESSAGES_STUDENT,
        max_messages_teacher=_config_module.CHAT_MAX_MESSAGES_TEACHER,
        max_chars=_config_module.CHAT_MAX_MESSAGE_CHARS,
    )


def _student_inflight(student_id: Optional[str]) -> Any:
    mod = sys.modules[__name__]
    return _student_inflight_guard_impl(
        student_id=student_id,
        inflight=getattr(mod, "_STUDENT_INFLIGHT", {}),
        lock=getattr(mod, "_STUDENT_INFLIGHT_LOCK", threading.Lock()),
        limit=_config_module.CHAT_STUDENT_INFLIGHT_LIMIT,
    )

def _setup_diag_logger() -> Optional[logging.Logger]:
    if not _config_module.DIAG_LOG_ENABLED:
        return None
    _config_module.DIAG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("diag")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        str(_config_module.DIAG_LOG_PATH), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


_DIAG_LOGGER = _setup_diag_logger()
LLM_GATEWAY = LLMGateway()

def diag_log(event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    if not _config_module.DIAG_LOG_ENABLED or _DIAG_LOGGER is None:
        return
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
    }
    if payload:
        record.update(payload)
    try:
        _DIAG_LOGGER.info(json.dumps(record, ensure_ascii=False, default=str))
    except Exception:  # policy: allowed-broad-except
        _log.debug("diag_log serialization failed for event=%s", event)
        pass  # policy: allowed-broad-except

def chat_job_path(job_id: str) -> Path:
    return _core_service_imports_module._chat_job_path_impl(
        job_id, deps=_app_core_wiring_exports_module.chat_job_repo_deps(CURRENT_CORE.get(None))
    )

def load_chat_job(job_id: str) -> Dict[str, Any]:
    return _core_service_imports_module._load_chat_job_impl(
        job_id, deps=_app_core_wiring_exports_module.chat_job_repo_deps(CURRENT_CORE.get(None))
    )

def write_chat_job(job_id: str, updates: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    return _core_service_imports_module._write_chat_job_impl(
        job_id,
        updates,
        deps=_app_core_wiring_exports_module.chat_job_repo_deps(CURRENT_CORE.get(None)),
        overwrite=overwrite,
    )

def _inline_backend_factory():
    return _app_core_init_module.build_inline_backend_factory(
        current_core=CURRENT_CORE.get(None),
        app_core_wiring_exports_module=_app_core_wiring_exports_module,
        core_service_imports_module=_core_service_imports_module,
        profile_update_async=_config_module.PROFILE_UPDATE_ASYNC,
    )
