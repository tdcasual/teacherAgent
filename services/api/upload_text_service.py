from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from fastapi import UploadFile

_log = logging.getLogger(__name__)

_OCR_UTILS: Optional[Tuple[Any, Any]] = None


@dataclass(frozen=True)
class UploadTextDeps:
    diag_log: Callable[..., None]
    limit: Callable[[Any], Any]
    ocr_semaphore: Any


def parse_timeout_env(name: str) -> Optional[float]:
    raw = os.getenv(name)
    if raw is None:
        return None
    val = raw.strip().lower()
    if not val:
        return None
    if val in {"0", "none", "inf", "infinite", "null"}:
        return None
    try:
        return float(val)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None


async def save_upload_file(
    upload: UploadFile,
    dest: Path,
    *,
    run_in_threadpool: Callable[[Callable[..., Any]], Any],
    chunk_size: int = 1024 * 1024,
) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _copy() -> int:
        total = 0
        try:
            upload.file.seek(0)
        except Exception:
            _log.debug("operation failed", exc_info=True)
            pass
        with dest.open("wb") as out:
            while True:
                chunk = upload.file.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                total += len(chunk)
        return total

    return await run_in_threadpool(_copy)


def ensure_ocr_api_key_aliases() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        for alias in ("openai-api-key", "OPENAI-API-KEY", "openai_api_key", "openaiApiKey"):
            value = os.environ.get(alias)
            if value:
                os.environ["OPENAI_API_KEY"] = value.strip()
                break
    if not os.getenv("SILICONFLOW_API_KEY"):
        for alias in ("siliconflow-api-key", "SILICONFLOW-API-KEY", "siliconflow_api_key"):
            value = os.environ.get(alias)
            if value:
                os.environ["SILICONFLOW_API_KEY"] = value.strip()
                break


def load_ocr_utils() -> Tuple[Any, Any]:
    global _OCR_UTILS
    if _OCR_UTILS is not None:
        return _OCR_UTILS
    try:
        from ocr_utils import load_env_from_dotenv, ocr_with_sdk  # type: ignore

        # Load once on first use; repeated file reads can become a hot-path under load.
        load_env_from_dotenv(Path(".env"))
        ensure_ocr_api_key_aliases()
        _OCR_UTILS = (load_env_from_dotenv, ocr_with_sdk)
        return _OCR_UTILS
    except Exception:
        _log.debug("operation failed", exc_info=True)
        _OCR_UTILS = (None, None)
        return _OCR_UTILS


def clean_ocr_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines)


def extract_text_from_pdf(
    path: Path,
    *,
    deps: UploadTextDeps,
    language: str = "zh",
    ocr_mode: str = "FREE_OCR",
    prompt: str = "",
) -> str:
    text = ""
    try:
        import pdfplumber  # type: ignore
        t1 = time.monotonic()
        pages_text = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    pages_text.append(page_text)
        text = "\n".join(pages_text)
        deps.diag_log(
            "pdf.extract.done",
            {"file": str(path), "duration_ms": int((time.monotonic() - t1) * 1000)},
        )
    except Exception as exc:
        _log.debug("numeric conversion failed", exc_info=True)
        deps.diag_log("pdf.extract.error", {"file": str(path), "error": str(exc)[:200]})

    if len(text.strip()) >= 50:
        return clean_ocr_text(text)

    ocr_text = ""
    ocr_timeout = parse_timeout_env("OCR_TIMEOUT_SEC")
    _, ocr_with_sdk = load_ocr_utils()
    if ocr_with_sdk:
        try:
            t0 = time.monotonic()
            with deps.limit(deps.ocr_semaphore):
                ocr_text = ocr_with_sdk(path, language=language, mode=ocr_mode, prompt=prompt, timeout=ocr_timeout)
            deps.diag_log(
                "pdf.ocr.done",
                {
                    "file": str(path),
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "timeout": ocr_timeout,
                },
            )
        except Exception as exc:
            _log.debug("numeric conversion failed", exc_info=True)
            deps.diag_log("pdf.ocr.error", {"file": str(path), "error": str(exc)[:200], "timeout": ocr_timeout})
            if "OCR unavailable" in str(exc) or "Missing OCR SDK" in str(exc):
                raise

    if len(ocr_text.strip()) >= 50:
        return clean_ocr_text(ocr_text)
    if ocr_text:
        return clean_ocr_text(ocr_text)
    return clean_ocr_text(text)


def extract_text_from_image(
    path: Path,
    *,
    deps: UploadTextDeps,
    language: str = "zh",
    ocr_mode: str = "FREE_OCR",
    prompt: str = "",
) -> str:
    _, ocr_with_sdk = load_ocr_utils()
    if not ocr_with_sdk:
        raise RuntimeError("OCR unavailable: ocr_utils not available")
    try:
        ocr_timeout = parse_timeout_env("OCR_TIMEOUT_SEC")
        t0 = time.monotonic()
        with deps.limit(deps.ocr_semaphore):
            ocr_text = ocr_with_sdk(path, language=language, mode=ocr_mode, prompt=prompt, timeout=ocr_timeout)
        deps.diag_log(
            "image.ocr.done",
            {
                "file": str(path),
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "timeout": ocr_timeout,
            },
        )
        return clean_ocr_text(ocr_text)
    except Exception as exc:
        deps.diag_log("image.ocr.error", {"file": str(path), "error": str(exc)[:200]})
        raise


def extract_text_from_file(
    path: Path,
    *,
    deps: UploadTextDeps,
    language: str = "zh",
    ocr_mode: str = "FREE_OCR",
    prompt: str = "",
) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path, deps=deps, language=language, ocr_mode=ocr_mode, prompt=prompt)
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        return extract_text_from_image(path, deps=deps, language=language, ocr_mode=ocr_mode, prompt=prompt)
    if suffix in {".md", ".markdown", ".tex", ".txt"}:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            _log.debug("file read failed", exc_info=True)
            text = path.read_text(errors="ignore")
        if suffix == ".tex":
            lines = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("%"):
                    continue
                lines.append(line)
            text = "\n".join(lines)
        return clean_ocr_text(text)
    raise RuntimeError(f"不支持的文件类型：{suffix or path.name}")
