#!/usr/bin/env python3
import base64
import json
import os
import mimetypes
from pathlib import Path
from typing import Optional


_DOTENV_LOADED = False


def load_env_from_dotenv(dotenv_path: Optional[Path] = None):
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
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
    _DOTENV_LOADED = True


def ocr_with_sdk(
    file_path: Path,
    mode: str = "FREE_OCR",
    language: str = "zh",
    prompt: str = "",
    timeout: Optional[float] = None,
) -> str:
    # Ensure .env is loaded when used outside the FastAPI loader.
    try:
        load_env_from_dotenv(Path(".env"))
    except Exception:
        pass

    # Prefer SDKs when available; otherwise fall back to a direct OpenAI-compatible HTTP call.
    client = None
    sdk_error: Optional[Exception] = None
    base_url = os.getenv("DS_OCR_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1"
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY") or ""
    model = os.getenv("SILICONFLOW_OCR_MODEL", "deepseek-ai/DeepSeek-OCR")

    def normalize_chat_url(url: str) -> str:
        url = (url or "").rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        # If caller provides a host without /v1, assume OpenAI-compatible layout.
        if url.endswith("/v1/chat/completions"):
            return url
        return url + "/v1/chat/completions"

    try:
        from deepseek_ocr import DeepSeekOCR  # type: ignore

        client = DeepSeekOCR(
            api_key=api_key,
            base_url=normalize_chat_url(base_url),
            model=model,
        )
    except Exception as exc:
        sdk_error = exc
        try:
            from multi_ocr_sdk import DeepSeekOCR  # type: ignore

            client = DeepSeekOCR(
                api_key=api_key,
                base_url=normalize_chat_url(base_url),
            )
            sdk_error = None
        except Exception as exc2:
            sdk_error = exc2

    if client is None:
        # Direct HTTP fallback (no extra dependencies).
        if not api_key:
            raise RuntimeError("OCR unavailable: missing OPENAI_API_KEY/SILICONFLOW_API_KEY") from sdk_error
        try:
            import requests

            mime, _ = mimetypes.guess_type(str(file_path))
            mime = mime or "application/octet-stream"
            data_url = f"data:{mime};base64,{ocr_image_base64(file_path)}"
            chat_url = normalize_chat_url(base_url)
            text_prompt = prompt or "请做OCR，仅返回识别出的原始文本（尽量保留换行与题号）。"
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                "temperature": 0,
            }
            if timeout is not None:
                payload["timeout"] = timeout
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            resp = requests.post(chat_url, headers=headers, json=payload, timeout=timeout or 60)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content or ""
        except Exception as exc:
            raise RuntimeError(f"OCR request failed: {exc}") from exc

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
