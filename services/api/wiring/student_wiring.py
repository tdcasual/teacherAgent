"""Student domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "_student_submit_deps",
    "_student_profile_api_deps",
    "_student_import_deps",
    "_student_directory_deps",
    "_student_ops_api_deps",
]

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..student_directory_service import StudentDirectoryDeps
from ..student_import_service import StudentImportDeps
from ..student_ops_api_service import StudentOpsApiDeps
from ..student_profile_api_service import StudentProfileApiDeps
from ..student_submit_service import StudentSubmitDeps


from . import get_app_core as _app_core


def _student_submit_deps():
    _ac = _app_core()
    return StudentSubmitDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        app_root=_ac.APP_ROOT,
        student_submissions_dir=_ac.STUDENT_SUBMISSIONS_DIR,
        run_script=_ac.run_script,
        sanitize_filename=_ac.sanitize_filename,
    )


def _student_profile_api_deps():
    _ac = _app_core()
    return StudentProfileApiDeps(student_profile_get=_ac.student_profile_get)


def _student_import_deps():
    _ac = _app_core()
    return StudentImportDeps(
        app_root=_ac.APP_ROOT,
        data_dir=_ac.DATA_DIR,
        load_profile_file=_ac.load_profile_file,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _student_directory_deps():
    _ac = _app_core()
    return StudentDirectoryDeps(
        data_dir=_ac.DATA_DIR,
        load_profile_file=_ac.load_profile_file,
        normalize=_ac.normalize,
    )


def _student_ops_api_deps():
    _ac = _app_core()
    return StudentOpsApiDeps(
        uploads_dir=_ac.UPLOADS_DIR,
        app_root=_ac.APP_ROOT,
        sanitize_filename=_ac.sanitize_filename,
        save_upload_file=_ac.save_upload_file,
        run_script=_ac.run_script,
        student_candidates_by_name=_ac.student_candidates_by_name,
        normalize=_ac.normalize,
        diag_log=_ac.diag_log,
    )
