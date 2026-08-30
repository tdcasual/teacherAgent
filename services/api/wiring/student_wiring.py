"""Student domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "student_submit_deps",
    "student_import_deps",
    "student_directory_deps",
    "student_ops_deps",
    "assignment_process_archive_deps",
    "_student_submit_deps",
    "_student_import_deps",
    "_student_directory_deps",
    "_student_ops_deps",
]

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from services.api.runtime import queue_runtime

from ..assignment_process_archive_service import (
    AssignmentProcessArchiveDeps,
    trigger_on_submit,
)
from ..assignment_student_list_service import student_currently_enrolled
from ..auth_registry_service import build_auth_registry_store
from ..paths import student_session_file
from ..session_store import load_student_sessions_index
from ..student_directory_service import StudentDirectoryDeps
from ..student_import_service import StudentImportDeps
from ..student_memory_service import (
    StudentMemoryDeps,
)
from ..student_memory_service import (
    student_memory_auto_propose_from_assignment_evidence_api as _student_memory_auto_propose_from_assignment_evidence_api,
)
from ..student_ops_service import StudentOpsDeps
from ..student_submit_service import StudentSubmitDeps
from . import get_app_core as _app_core

_log = logging.getLogger(__name__)


def _load_assignment_teacher_id(assignment_id: str, core) -> str | None:
    try:
        folder = core.resolve_assignment_dir(assignment_id)
        meta = core.load_assignment_meta(folder)
    except Exception:  # policy: allowed-broad-except
        return None
    if not isinstance(meta, dict):
        return None
    teacher_id = str(meta.get("teacher_id") or "").strip()
    return teacher_id or None


def _load_student_sessions(student_id: str, assignment_id: str) -> List[str]:
    items = load_student_sessions_index(student_id)
    session_ids: List[str] = []
    aid = str(assignment_id or "").strip()
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("assignment_id") or "").strip() != aid:
            continue
        sid = str(item.get("session_id") or "").strip()
        if sid:
            session_ids.append(sid)
    return session_ids


def _load_session_turns(student_id: str, session_id: str) -> List[Dict[str, Any]]:
    path = student_session_file(student_id, session_id)
    if not path.exists():
        return []
    turns: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        _log.debug("failed to read session file %s", path, exc_info=True)
        return []
    for line in lines:
        text = (line or "").strip()
        if not text:
            continue
        try:
            rec = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            turns.append(rec)
    return turns


def _queue_backend_for_core(core: Any) -> Any:
    return queue_runtime.app_queue_backend(
        tenant_id=getattr(core, "TENANT_ID", None) or None,
        is_pytest=core._settings.is_pytest(),
        inline_backend_factory=core._inline_backend_factory,
    )


def assignment_process_archive_deps(core=None) -> AssignmentProcessArchiveDeps:
    _ac = _app_core(core)
    return AssignmentProcessArchiveDeps(
        data_dir=_ac.DATA_DIR,
        load_assignment_meta=_ac.load_assignment_meta,
        load_student_sessions=_load_student_sessions,
        load_session_turns=_load_session_turns,
        call_llm=lambda messages, timeout_sec=20.0, **_kwargs: _ac.call_llm(
            messages,
            role_hint="teacher",
            kind="assignment.process_archive",
        ),
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        diag_log=_ac.diag_log,
        monotonic=time.monotonic,
        new_id=lambda: f"parch_{uuid.uuid4().hex[:16]}",
        student_enrolled=lambda sid, tid, sub: student_currently_enrolled(
            sid, tid, sub, data_dir=_ac.DATA_DIR
        ),
    )


def _student_submit_deps(core=None):
    _ac = _app_core(core)
    student_memory_deps = StudentMemoryDeps(
        resolve_teacher_id=_ac.require_teacher_id,
        teacher_workspace_dir=_ac.teacher_workspace_dir,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        assignment_evidence_high_mastery_ratio=_ac.STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_HIGH_MASTERY_RATIO,
        assignment_evidence_low_mastery_ratio=_ac.STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_LOW_MASTERY_RATIO,
    )
    archive_deps = assignment_process_archive_deps(_ac)
    backend = _queue_backend_for_core(_ac)

    def _trigger(**kwargs: Any) -> Dict[str, Any]:
        return trigger_on_submit(
            assignment_id=str(kwargs.get("assignment_id") or ""),
            student_id=str(kwargs.get("student_id") or ""),
            reason=str(kwargs.get("reason") or "submit"),
            deps=archive_deps,
            enqueue=lambda payload: queue_runtime.enqueue_process_archive(payload, backend=backend),
        )

    return StudentSubmitDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        app_root=_ac.APP_ROOT,
        student_submissions_dir=_ac.STUDENT_SUBMISSIONS_DIR,
        run_script=_ac.run_script,
        sanitize_filename=_ac.sanitize_filename,
        compute_assignment_progress=_ac.compute_assignment_progress,
        student_memory_auto_propose_from_assignment_evidence=lambda **kwargs: _student_memory_auto_propose_from_assignment_evidence_api(
            deps=student_memory_deps,
            teacher_id=kwargs.get("teacher_id"),
            student_id=str(kwargs.get("student_id") or ""),
            assignment_id=str(kwargs.get("assignment_id") or ""),
            evidence=kwargs.get("evidence") if isinstance(kwargs.get("evidence"), dict) else None,
            request_id=(str(kwargs.get("request_id") or "") or None),
        ),
        load_assignment_teacher_id=lambda assignment_id: _load_assignment_teacher_id(assignment_id, _ac),
        diag_log=_ac.diag_log,
        save_upload_file=_ac.save_upload_file,
        trigger_process_archive=_trigger,
    )


def _student_import_deps(core=None):
    _ac = _app_core(core)
    app_root = getattr(_ac, "APP_ROOT")
    return StudentImportDeps(
        app_root=app_root,
        data_dir=_ac.DATA_DIR,
        load_profile_file=_ac.load_profile_file,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _student_directory_deps(core=None):
    _ac = _app_core(core)
    return StudentDirectoryDeps(
        data_dir=_ac.DATA_DIR,
        load_profile_file=_ac.load_profile_file,
        normalize=_ac.normalize,
    )


def _student_ops_deps(core=None):
    _ac = _app_core(core)
    store = build_auth_registry_store(data_dir=_ac.DATA_DIR)
    return StudentOpsDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        app_root=_ac.APP_ROOT,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        run_script=_ac.run_script,
        student_candidates_by_name=_ac.student_candidates_by_name,
        normalize=_ac.normalize,
        diag_log=_ac.diag_log,
        issue_student_candidate_id=lambda sid: store.issue_opaque_candidate_id(
            role="student",
            subject_id=str(sid or ""),
        ),
    )


def student_submit_deps(core):
    return _student_submit_deps(core)


def student_import_deps(core):
    return _student_import_deps(core)


def student_directory_deps(core):
    return _student_directory_deps(core)


def student_ops_deps(core):
    return _student_ops_deps(core)
