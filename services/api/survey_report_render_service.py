from __future__ import annotations

from typing import Any, Dict, List


def _signal_line(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    detail = str(item.get("detail") or "").strip()
    refs = [str(ref) for ref in item.get("evidence_refs") or [] if str(ref).strip()]
    ref_suffix = f"（证据：{', '.join(refs)}）" if refs else ""
    return f"- {title}：{detail}{ref_suffix}".strip()



def _group_line(item: Dict[str, Any]) -> str:
    return f"- {str(item.get('group_name') or '班级差异').strip()}：{str(item.get('summary') or '').strip()}".strip()



def render_survey_report(
    *,
    report: Dict[str, Any],
    analysis_artifact: Dict[str, Any],
    bundle_meta: Dict[str, Any],
) -> Dict[str, Any]:
    executive_summary = str(analysis_artifact.get("executive_summary") or "").strip()
    key_signals = [item for item in analysis_artifact.get("key_signals") or [] if isinstance(item, dict)]
    group_differences = [item for item in analysis_artifact.get("group_differences") or [] if isinstance(item, dict)]
    teaching_recommendations = [str(item) for item in analysis_artifact.get("teaching_recommendations") or [] if str(item or "").strip()]
    confidence_and_gaps = analysis_artifact.get("confidence_and_gaps") or {}
    confidence = confidence_and_gaps.get("confidence")
    gaps = [str(item) for item in confidence_and_gaps.get("gaps") or [] if str(item or "").strip()]

    lines: List[str] = [
        "# 问卷分析报告",
        f"- 报告ID：{str(report.get('report_id') or '').strip()}",
        f"- 班级：{str(report.get('class_name') or '').strip() or '未知班级'}",
        f"- 状态：{str(report.get('status') or '').strip() or 'unknown'}",
        "",
        "## 核心结论",
        executive_summary or "暂无核心结论。",
        "",
        "## 关键信号",
    ]
    lines.extend(_signal_line(item) for item in key_signals) if key_signals else lines.append("- 暂无关键信号。")
    lines.extend([
        "",
        "## 分组差异",
    ])
    lines.extend(_group_line(item) for item in group_differences) if group_differences else lines.append("- 暂无分组差异。")
    lines.extend([
        "",
        "## 教学建议",
    ])
    if teaching_recommendations:
        lines.extend(f"- {item}" for item in teaching_recommendations)
    else:
        lines.append("- 暂无教学建议。")
    lines.extend([
        "",
        "## 置信度与缺口",
        f"- 分析置信度：{confidence}",
        f"- 证据置信度：{bundle_meta.get('parse_confidence')}",
        f"- 信息缺口：{', '.join(gaps) if gaps else '无'}",
    ])

    return {
        "summary": executive_summary,
        "markdown": "\n".join(lines).strip() + "\n",
        "json": {
            "report": dict(report),
            "analysis_artifact": dict(analysis_artifact),
            "bundle_meta": dict(bundle_meta),
        },
    }
