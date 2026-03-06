from __future__ import annotations

from typing import Any, Dict


def build_exam_analysis_workflow(req: Any, *, last_user_text: str, attachment_context: str) -> Dict[str, Any]:
    del req, attachment_context
    return {
        "workflow_id": "exam_analysis",
        "workflow_label": "考试分析",
        "extra_system": (
            "当前任务进入考试分析 workflow。请先确认考试范围、数据来源与分数模式，"
            "优先给出结论摘要，再补充班级概览、题目洞察、学生分层与讲评建议。"
            "若关键信息缺失，只追问最少 1–2 项。"
        ),
        "query_preview": str(last_user_text or "")[:160],
    }
