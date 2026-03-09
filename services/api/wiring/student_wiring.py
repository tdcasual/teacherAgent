"""Student domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "student_submit_deps",
    "student_import_deps",
    "student_directory_deps",
    "student_ops_deps",
    "_student_submit_deps",
    "_student_import_deps",
    "_student_directory_deps",
    "_student_ops_deps",
]

from datetime import datetime

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


def _student_submit_deps(core=None):
    _ac = _app_core(core)
    resolve_teacher_id = _ac.resolve_teacher_id
    student_memory_deps = StudentMemoryDeps(
        resolve_teacher_id=resolve_teacher_id,
        teacher_workspace_dir=_ac.teacher_workspace_dir,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        assignment_evidence_high_mastery_ratio=_ac.STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_HIGH_MASTERY_RATIO,
        assignment_evidence_low_mastery_ratio=_ac.STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_LOW_MASTERY_RATIO,
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
        resolve_teacher_id=resolve_teacher_id,
        diag_log=_ac.diag_log,
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
    return StudentOpsDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        app_root=_ac.APP_ROOT,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        run_script=_ac.run_script,
        student_candidates_by_name=_ac.student_candidates_by_name,
        normalize=_ac.normalize,
        diag_log=_ac.diag_log,
    )


def student_submit_deps(core):
    return _student_submit_deps(core)


def student_import_deps(core):
    return _student_import_deps(core)


def student_directory_deps(core):
    return _student_directory_deps(core)


def student_ops_deps(core):
    return _student_ops_deps(core)
