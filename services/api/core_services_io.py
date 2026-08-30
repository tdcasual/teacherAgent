from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .assignment_requirements_service import (
    compute_requirements_missing as _compute_requirements_missing_impl,
)
from .assignment_requirements_service import (
    merge_requirements as _merge_requirements_impl,
)
from .assignment_upload_parse_service import process_upload_job as _process_upload_job_impl
from .assignment_uploaded_question_service import (
    write_uploaded_questions as _write_uploaded_questions_impl,
)
from .core_utils import normalize_excel_cell as _normalize_excel_cell_impl
from .upload_llm_service import (
    llm_autofill_requirements as _llm_autofill_requirements_impl,
)
from .upload_llm_service import (
    llm_parse_assignment_payload as _llm_parse_assignment_payload_impl,
)
from .upload_llm_service import (
    parse_llm_json as _parse_llm_json_impl,
)
from .upload_llm_service import (
    summarize_questions_for_prompt as _summarize_questions_for_prompt_impl,
)
from .upload_llm_service import (
    truncate_text as _truncate_text_impl,
)
from .upload_llm_service import (
    xls_to_table_preview as _xls_to_table_preview_impl,
)
from .upload_llm_service import (
    xlsx_to_table_preview as _xlsx_to_table_preview_impl,
)
from .upload_text_service import (
    clean_ocr_text as _clean_ocr_text_impl,
)
from .upload_text_service import (
    extract_text_from_file as _extract_text_from_file_impl,
)
from .upload_text_service import (
    extract_text_from_image as _extract_text_from_image_impl,
)
from .upload_text_service import (
    extract_text_from_pdf as _extract_text_from_pdf_impl,
)
from .upload_text_service import (
    load_ocr_utils as _load_ocr_utils_impl,
)
from .upload_text_service import (
    parse_timeout_env as _parse_timeout_env_impl,
)
from .wiring.assignment_wiring import (
    _assignment_upload_parse_deps,
    _assignment_uploaded_question_deps,
)
from .wiring.misc_wiring import _upload_llm_deps, _upload_text_deps


def parse_timeout_env(name: str) -> Optional[float]:
    return _parse_timeout_env_impl(name)


def load_ocr_utils():
    return _load_ocr_utils_impl()


def clean_ocr_text(text: str) -> str:
    return _clean_ocr_text_impl(text)


def extract_text_from_pdf(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return _extract_text_from_pdf_impl(
        path,
        deps=_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )


def extract_text_from_file(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return _extract_text_from_file_impl(
        path,
        deps=_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )


def extract_text_from_image(path: Path, language: str = "zh", ocr_mode: str = "FREE_OCR", prompt: str = "") -> str:
    return _extract_text_from_image_impl(
        path,
        deps=_upload_text_deps(),
        language=language,
        ocr_mode=ocr_mode,
        prompt=prompt,
    )


def truncate_text(text: str, limit: int = 12000) -> str:
    return _truncate_text_impl(text, limit)


def parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    return _parse_llm_json_impl(content)


def llm_parse_assignment_payload(source_text: str, answer_text: str) -> Dict[str, Any]:
    return _llm_parse_assignment_payload_impl(source_text, answer_text, deps=_upload_llm_deps())


def summarize_questions_for_prompt(questions: List[Dict[str, Any]], limit: int = 4000) -> str:
    return _summarize_questions_for_prompt_impl(questions, limit=limit)


def compute_requirements_missing(requirements: Dict[str, Any]) -> List[str]:
    return _compute_requirements_missing_impl(requirements)


def merge_requirements(base: Dict[str, Any], update: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    return _merge_requirements_impl(base, update, overwrite=overwrite)


def llm_autofill_requirements(
    source_text: str,
    answer_text: str,
    questions: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    missing: List[str],
) -> Tuple[Dict[str, Any], List[str], bool]:
    return _llm_autofill_requirements_impl(
        source_text,
        answer_text,
        questions,
        requirements,
        missing,
        deps=_upload_llm_deps(),
    )


def process_upload_job(job_id: str) -> None:
    _process_upload_job_impl(job_id, deps=_assignment_upload_parse_deps())


def normalize_excel_cell(value: Any) -> str:
    return _normalize_excel_cell_impl(value)


def xlsx_to_table_preview(path: Path, max_rows: int = 60, max_cols: int = 30) -> str:
    return _xlsx_to_table_preview_impl(path, deps=_upload_llm_deps(), max_rows=max_rows, max_cols=max_cols)


def xls_to_table_preview(path: Path, max_rows: int = 60, max_cols: int = 30) -> str:
    return _xls_to_table_preview_impl(path, deps=_upload_llm_deps(), max_rows=max_rows, max_cols=max_cols)


def write_uploaded_questions(out_dir: Path, assignment_id: str, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _write_uploaded_questions_impl(
        out_dir,
        assignment_id,
        questions,
        deps=_assignment_uploaded_question_deps(),
    )
