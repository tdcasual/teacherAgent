from __future__ import annotations

from typing import Any, Dict


def build_student_focus_workflow(req: Any, *, last_user_text: str, attachment_context: str) -> Dict[str, Any]:
    del attachment_context
    student_id = str(getattr(req, "student_id", "") or "").strip()
    return {
        "workflow_id": "student_focus",
        "workflow_label": "学生重点分析",
        "student_id": student_id,
        "extra_system": (
            "当前任务进入学生重点分析 workflow。请先锁定单个学生，再聚焦最近考试/作业证据，"
            "输出薄弱点、可能原因、后续干预建议。若学生身份未明确，只追问一次定位信息。"
        ),
        "query_preview": str(last_user_text or "")[:160],
    }
