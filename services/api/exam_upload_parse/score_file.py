from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .image_parser import parse_image_score_file
from .pdf_parser import parse_pdf_score_file
from .xls_parser import parse_xls_score_file
from .xlsx_parser import parse_xlsx_score_file

_log = logging.getLogger(__name__)


def parse_score_rows_for_file(
    *,
    exam_id: str,
    idx: int,
    fname: str,
    score_path: Path,
    derived_dir: Path,
    class_name_hint: str,
    selected_candidate_id: Optional[str],
    language: str,
    ocr_mode: str,
    deps: Any,
) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
    file_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    schema_source: Optional[Dict[str, Any]] = None
    try:
        suffix = score_path.suffix.lower()
        if suffix == ".xlsx":
            file_rows, warnings, schema_source = parse_xlsx_score_file(
                exam_id=exam_id,
                idx=idx,
                fname=fname,
                score_path=score_path,
                derived_dir=derived_dir,
                class_name_hint=class_name_hint,
                selected_candidate_id=selected_candidate_id,
                deps=deps,
            )
        elif suffix == ".xls":
            file_rows, warnings, schema_source = parse_xls_score_file(
                exam_id=exam_id,
                fname=fname,
                score_path=score_path,
                deps=deps,
            )
        elif suffix == ".pdf":
            file_rows, warnings, schema_source = parse_pdf_score_file(
                exam_id=exam_id,
                fname=fname,
                score_path=score_path,
                language=language,
                ocr_mode=ocr_mode,
                deps=deps,
            )
        else:
            file_rows, warnings, schema_source = parse_image_score_file(
                exam_id=exam_id,
                fname=fname,
                score_path=score_path,
                language=language,
                ocr_mode=ocr_mode,
                deps=deps,
            )
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        warnings.append(f"成绩文件 {fname} 解析异常：{str(exc)[:120]}")
    return file_rows, warnings, schema_source
