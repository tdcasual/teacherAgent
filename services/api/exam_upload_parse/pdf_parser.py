from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .preview import parse_rows_from_table_preview


def parse_pdf_score_file(
    *,
    exam_id: str,
    fname: str,
    score_path: Path,
    language: str,
    ocr_mode: str,
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
    score_text_parts: List[str] = [
        deps.extract_text_from_pdf(score_path, language=language, ocr_mode=ocr_mode)
    ]
    preview_rows, preview_warnings = parse_rows_from_table_preview(
        exam_id=exam_id,
        fname=fname,
        table_preview="\n\n".join([text for text in score_text_parts if text]),
        deps=deps,
    )
    return preview_rows, preview_warnings, None
