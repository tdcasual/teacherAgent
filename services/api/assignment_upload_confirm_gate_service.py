from __future__ import annotations

from typing import Any, Dict, Optional


class AssignmentUploadConfirmGateError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def ensure_assignment_upload_confirm_ready(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    status = job.get("status")
    if status == "confirmed":
        return {
            "ok": True,
            "assignment_id": job.get("assignment_id"),
            "status": "confirmed",
            "message": "作业已创建（已确认）。",
        }
    if status != "done":
        raise AssignmentUploadConfirmGateError(
            400,
            {
                "error": "job_not_ready",
                "message": "解析尚未完成，请稍后再创建作业。",
                "status": status,
                "step": job.get("step"),
                "progress": job.get("progress"),
            },
        )
    return None
