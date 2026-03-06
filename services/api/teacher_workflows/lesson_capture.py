from __future__ import annotations

from typing import Any, Dict


def build_lesson_capture_workflow(req: Any, *, last_user_text: str, attachment_context: str) -> Dict[str, Any]:
    del req
    return {
        "workflow_id": "lesson_capture",
        "workflow_label": "课堂材料采集",
        "has_attachment_context": bool(str(attachment_context or "").strip()),
        "extra_system": (
            "当前任务进入课堂材料采集 workflow。请优先抽取板书、课堂图片或讲义中的知识点、例题与讨论结构，"
            "再整理成可复用讲义；若材料缺失，明确提示上传或补充课堂编号。"
        ),
        "query_preview": str(last_user_text or "")[:160],
    }
