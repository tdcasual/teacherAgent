from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .preview import parse_rows_from_table_preview

_log = logging.getLogger(__name__)


def parse_xls_score_file(
    *,
    exam_id: str,
    fname: str,
    score_path: Path,
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
    file_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    try:
        preview_rows, preview_warnings = parse_rows_from_table_preview(
            exam_id=exam_id,
            fname=fname,
            table_preview=deps.xls_to_table_preview(score_path),
            deps=deps,
        )
        file_rows = preview_rows
        warnings.extend(preview_warnings)
    except Exception as exc:  # policy: allowed-broad-except
        # Per-file catch: parent turned a raise into a warning instead of aborting the job.
        _log.debug("operation failed", exc_info=True)
        warnings.append(f"成绩文件 {fname} 解析异常：{str(exc)[:120]}")
    return file_rows, warnings, None
