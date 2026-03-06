from __future__ import annotations

from typing import Any, Dict


def build_homework_generation_workflow(req: Any, *, last_user_text: str, attachment_context: str) -> Dict[str, Any]:
    del attachment_context
    return {
        "workflow_id": "homework_generation",
        "workflow_label": "作业生成",
        "assignment_id": str(getattr(req, "assignment_id", "") or "").strip(),
        "extra_system": (
            "当前任务进入作业生成 workflow。请先确认作业约束、知识点、题量与交付范围，"
            "再生成题目或要求；若缺关键字段，优先返回最小补充清单。"
        ),
        "query_preview": str(last_user_text or "")[:160],
    }
