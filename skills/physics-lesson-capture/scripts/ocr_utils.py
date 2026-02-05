#!/usr/bin/env python3
import base64
import json
import os
from pathlib import Path
from typing import Optional


def load_env_from_dotenv(dotenv_path: Optional[Path] = None):
    path = dotenv_path or Path('.env')
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def ocr_with_sdk(
    file_path: Path,
    mode: str = "FREE_OCR",
    language: str = "zh",
    prompt: str = "",
    timeout: Optional[float] = None,
) -> str:
    # Try deepseek-ocr or multi-ocr-sdk
    client = None
    try:
        from deepseek_ocr import DeepSeekOCR  # type: ignore
        base_url = os.getenv("DS_OCR_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1/chat/completions"
        if base_url.endswith("/v1"):
            base_url = base_url + "/chat/completions"
        client = DeepSeekOCR(
            api_key=os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY"),
            base_url=base_url,
            model=os.getenv("SILICONFLOW_OCR_MODEL", "deepseek-ai/DeepSeek-OCR"),
        )
    except Exception:
        try:
            from multi_ocr_sdk import DeepSeekOCR  # type: ignore
            base_url = os.getenv("DS_OCR_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1/chat/completions"
            if base_url.endswith("/v1"):
                base_url = base_url + "/chat/completions"
            client = DeepSeekOCR(
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY"),
                base_url=base_url,
            )
        except Exception as exc:
            raise RuntimeError(
                "Missing OCR SDK. Install one of: pip install deepseek-ocr  OR  pip install multi-ocr-sdk"
            ) from exc

    # Most SDKs expose parse(path, mode=..., language=..., prompt=...)
    if timeout is not None:
        if hasattr(client, "timeout"):
            try:
                setattr(client, "timeout", timeout)
            except Exception:
                pass
        if hasattr(client, "request_timeout"):
            try:
                setattr(client, "request_timeout", timeout)
            except Exception:
                pass

    kwargs = {}
    if mode:
        kwargs["mode"] = mode
    if language:
        kwargs["language"] = language
    if prompt:
        kwargs["prompt"] = prompt
    if timeout is not None:
        kwargs["timeout"] = timeout

    try:
        return client.parse(str(file_path), **kwargs)
    except TypeError:
        # Fallback if SDK doesn't accept kwargs
        return client.parse(str(file_path))


def ocr_image_base64(image_path: Path) -> str:
    data = image_path.read_bytes()
    return base64.b64encode(data).decode("utf-8")


def save_raw_ocr(out_path: Path, payload: dict):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
