from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .preview import parse_rows_from_table_preview


def parse_xls_score_file(
    *,
    exam_id: str,
    fname: str,
    score_path: Path,
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
    preview_rows, preview_warnings = parse_rows_from_table_preview(
        exam_id=exam_id,
        fname=fname,
        table_preview=deps.xls_to_table_preview(score_path),
        deps=deps,
    )
    return preview_rows, preview_warnings, None
