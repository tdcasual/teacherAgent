from __future__ import annotations

from typing import Any

from services.api.workers.chat_worker_service import start_chat_worker, stop_chat_worker
from services.api.workers.exam_worker_service import start_exam_upload_worker, stop_exam_upload_worker
from services.api.workers.profile_update_worker_service import start_profile_update_worker, stop_profile_update_worker
from services.api.workers.upload_worker_service import start_upload_worker, stop_upload_worker


def start_inline_workers(
    *, upload_deps: Any, exam_deps: Any, profile_deps: Any, chat_deps: Any, profile_update_async: bool
) -> None:
    start_upload_worker(deps=upload_deps)
    if profile_update_async:
        start_profile_update_worker(deps=profile_deps)
    start_exam_upload_worker(deps=exam_deps)
    start_chat_worker(deps=chat_deps)


def stop_inline_workers(
    *, upload_deps: Any, exam_deps: Any, profile_deps: Any, chat_deps: Any, profile_update_async: bool
) -> None:
    stop_chat_worker(deps=chat_deps)
    stop_exam_upload_worker(deps=exam_deps)
    stop_upload_worker(deps=upload_deps)
    if profile_update_async:
        stop_profile_update_worker(deps=profile_deps)
