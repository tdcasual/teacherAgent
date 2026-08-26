from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .preview import parse_rows_from_table_preview

_log = logging.getLogger(__name__)


def parse_image_score_file(
    *,
    exam_id: str,
    fname: str,
    score_path: Path,
    language: str,
    ocr_mode: str,
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
    file_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    try:
        score_text_parts: List[str] = [
            deps.extract_text_from_image(score_path, language=language, ocr_mode=ocr_mode)
        ]
        preview_rows, preview_warnings = parse_rows_from_table_preview(
            exam_id=exam_id,
            fname=fname,
            table_preview="\n\n".join([text for text in score_text_parts if text]),
            deps=deps,
        )
        file_rows = preview_rows
        warnings.extend(preview_warnings)
    except Exception as exc:  # policy: allowed-broad-except
        # Per-file catch: parent turned a raise into a warning instead of aborting the job.
        _log.debug("operation failed", exc_info=True)
        warnings.append(f"成绩文件 {fname} 解析异常：{str(exc)[:120]}")
    return file_rows, warnings, None
