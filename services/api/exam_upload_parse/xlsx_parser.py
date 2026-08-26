from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .preview import parse_rows_from_table_preview


def parse_xlsx_score_file(
    *,
    exam_id: str,
    idx: int,
    fname: str,
    score_path: Path,
    derived_dir: Path,
    class_name_hint: str,
    selected_candidate_id: Optional[str],
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
    warnings: List[str] = []
    schema_source: Optional[Dict[str, Any]] = None
    tmp_csv = derived_dir / f"responses_part_{idx}.csv"
    parsed_rows, parsed_score_schema = deps.parse_xlsx_with_script(
        score_path,
        tmp_csv,
        exam_id,
        class_name_hint,
        selected_candidate_id,
    )
    file_rows = parsed_rows or []
    if isinstance(parsed_score_schema, dict) and parsed_score_schema:
        schema_source = {
            "file": str(fname),
            "path": str(score_path),
            **parsed_score_schema,
        }
    if not file_rows:
        preview_rows, preview_warnings = parse_rows_from_table_preview(
            exam_id=exam_id,
            fname=fname,
            table_preview=deps.xlsx_to_table_preview(score_path),
            deps=deps,
        )
        file_rows = preview_rows
        warnings.extend(preview_warnings)
    return file_rows, warnings, schema_source
