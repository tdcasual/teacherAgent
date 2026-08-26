from __future__ import annotations

from typing import Any, Dict, List, Tuple


def parse_rows_from_table_preview(
    *,
    exam_id: str,
    fname: str,
    table_preview: str,
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not table_preview.strip():
        return [], []
    parsed_scores = deps.llm_parse_exam_scores(table_preview)
    if parsed_scores.get("error"):
        return [], [f"成绩文件 {fname} LLM解析失败：{parsed_scores.get('error')}"]
    file_rows, _, file_warnings = deps.build_exam_rows_from_parsed_scores(exam_id, parsed_scores)
    return file_rows, list(file_warnings or [])
