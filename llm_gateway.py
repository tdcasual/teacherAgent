from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os
from functools import lru_cache
import time
import random

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

import requests


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config" / "model_registry.yaml"


@dataclass
class UnifiedLLMRequest:
    messages: Optional[List[Dict[str, Any]]] = None
    input_text: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    json_schema: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = None
    stream: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedLLMResponse:
    text: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_chat_completion(self) -> Dict[str, Any]:
        message: Dict[str, Any] = {"content": self.text}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return {
            "choices": [{"message": message}],
            "usage": self.usage,
        }


@dataclass
class Target:
    provider: str
    mode: str
    model: str
    base_url: str
    endpoint: str
    headers: Dict[str, str]
    timeout_sec: Tuple[float, float]
    retry: int


def _load_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model registry not found: {path}")
    if yaml is None:
        raise RuntimeError("PyYAML is required to load model_registry.yaml. Install pyyaml.")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=8)
def _load_registry_cached(path_str: str) -> Dict[str, Any]:
    # Cached for performance; changes require process restart (reasonable for server runtime).
    return _load_registry(Path(path_str))


def _messages_to_response_input(messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    instructions: List[str] = []
    items: List[Dict[str, Any]] = []
    for msg in messages:
        role = (msg.get("role") or "user").strip()
        content = msg.get("content", "")
        if role in {"system", "developer"}:
            if content:
                instructions.append(str(content))
            continue
        items.append(
            {
                "role": role,
                "content": [
                    {
                        "type": "input_text",
                        "text": str(content),
                    }
                ],
            }
        )
    return "\n".join(instructions).strip(), items


def _build_json_schema_payload(schema: Dict[str, Any]) -> Dict[str, Any]:
    if not schema:
        return {}
    if "schema" in schema or "name" in schema:
        return {"type": "json_schema", "json_schema": schema}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "response",
            "schema": schema,
            "strict": True,
        },
    }


def _collect_tool_calls_from_responses(output: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tool_calls: List[Dict[str, Any]] = []
    for item in output or []:
        item_type = item.get("type", "")
        if "call" not in item_type:
            continue
        name = item.get("name") or item.get("tool_name") or item.get("function", {}).get("name")
        arguments = item.get("arguments") or item.get("args") or item.get("function", {}).get("arguments")
        if name:
            tool_calls.append(
                {
                    "id": item.get("id") or item.get("call_id") or item.get("tool_call_id") or "",
                    "type": "function",
                    "function": {"name": name, "arguments": arguments or ""},
                }
            )
    return tool_calls


def _response_text_from_output(output: List[Dict[str, Any]]) -> str:
    texts: List[str] = []
    for item in output or []:
        if item.get("type") != "message":
            continue
        for block in item.get("content") or []:
            if block.get("type") == "output_text":
                text = block.get("text")
                if text:
                    texts.append(text)
    return "\n".join(texts).strip()


def _clamp_timeout_seconds(value: Any, *, default: float, min_value: float = 1.0, max_value: float = 300.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = float(default)
    if parsed <= 0:
        parsed = float(default)
    return min(max_value, max(min_value, parsed))


def _parse_timeout_candidate(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"0", "none", "inf", "infinite", "null"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _build_timeout_pair(
    *,
    default_timeout_sec: Any,
    timeout_value: Any = None,
    connect_value: Any = None,
    read_value: Any = None,
) -> Tuple[float, float]:
    default_read = _clamp_timeout_seconds(default_timeout_sec, default=120.0)
    timeout_candidate = _parse_timeout_candidate(timeout_value)
    base_read = _clamp_timeout_seconds(timeout_candidate, default=default_read)
    read_candidate = _parse_timeout_candidate(read_value)
    read_timeout = _clamp_timeout_seconds(read_candidate, default=base_read)
    connect_default = min(10.0, read_timeout)
    connect_candidate = _parse_timeout_candidate(connect_value)
    connect_timeout = _clamp_timeout_seconds(connect_candidate, default=connect_default, max_value=120.0)
    connect_timeout = min(connect_timeout, read_timeout)
    return (connect_timeout, read_timeout)


class OpenAIResponsesAdapter:
    def __init__(self, target: Target, session: requests.Session):
        self.target = target
        self.session = session

    def generate(self, req: UnifiedLLMRequest) -> UnifiedLLMResponse:
        payload: Dict[str, Any] = {
            "model": self.target.model,
            "temperature": req.temperature,
            "stream": req.stream,
        }
        if req.max_tokens is not None:
            payload["max_output_tokens"] = req.max_tokens
        if req.messages:
            instructions, items = _messages_to_response_input(req.messages)
            if instructions:
                payload["instructions"] = instructions
            payload["input"] = items
        else:
            payload["input"] = req.input_text or ""

        if req.tools:
            payload["tools"] = req.tools
        if req.tool_choice is not None:
            payload["tool_choice"] = req.tool_choice
        if req.json_schema:
            payload["text"] = {"format": _build_json_schema_payload(req.json_schema)}

        resp = self.session.post(
            f"{self.target.base_url}{self.target.endpoint}",
            headers=self.target.headers,
            json=payload,
            timeout=self.target.timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("output_text") or _response_text_from_output(data.get("output") or [])
        tool_calls = _collect_tool_calls_from_responses(data.get("output") or [])
        return UnifiedLLMResponse(
            text=text or "",
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            finish_reason=data.get("status"),
            raw=data,
        )


class OpenAIChatAdapter:
    def __init__(self, target: Target, session: requests.Session):
        self.target = target
        self.session = session

    def generate(self, req: UnifiedLLMRequest) -> UnifiedLLMResponse:
        payload: Dict[str, Any] = {
            "model": self.target.model,
            "messages": req.messages or [{"role": "user", "content": req.input_text or ""}],
            "temperature": req.temperature,
            "stream": req.stream,
        }
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens
        if req.tools:
            payload["tools"] = req.tools
        if req.tool_choice is not None:
            payload["tool_choice"] = req.tool_choice
        if req.json_schema:
            payload["response_format"] = _build_json_schema_payload(req.json_schema)

        resp = self.session.post(
            f"{self.target.base_url}{self.target.endpoint}",
            headers=self.target.headers,
            json=payload,
            timeout=self.target.timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        text = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        finish_reason = data.get("choices", [{}])[0].get("finish_reason")
        return UnifiedLLMResponse(
            text=text,
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            finish_reason=finish_reason,
            raw=data,
        )


class OpenAICompletionsAdapter:
    def __init__(self, target: Target, session: requests.Session):
        self.target = target
        self.session = session

    def generate(self, req: UnifiedLLMRequest) -> UnifiedLLMResponse:
        payload: Dict[str, Any] = {
            "model": self.target.model,
            "prompt": req.input_text or "",
            "temperature": req.temperature,
            "stream": req.stream,
        }
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens

        resp = self.session.post(
            f"{self.target.base_url}{self.target.endpoint}",
            headers=self.target.headers,
            json=payload,
            timeout=self.target.timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("choices", [{}])[0].get("text", "")
        finish_reason = data.get("choices", [{}])[0].get("finish_reason")
        return UnifiedLLMResponse(
            text=text,
            usage=data.get("usage", {}),
            finish_reason=finish_reason,
            raw=data,
        )


class GeminiNativeAdapter:
    def __init__(self, target: Target, session: requests.Session):
        self.target = target
        self.session = session

    def generate(self, req: UnifiedLLMRequest) -> UnifiedLLMResponse:
        payload: Dict[str, Any] = {}
        if req.messages:
            # Minimal conversion: merge user/assistant into a single text block
            texts = []
            for msg in req.messages:
                role = msg.get("role") or "user"
                content = msg.get("content") or ""
                texts.append(f"{role}: {content}")
            payload["contents"] = [{"role": "user", "parts": [{"text": "\n".join(texts)}]}]
        else:
            payload["contents"] = [{"role": "user", "parts": [{"text": req.input_text or ""}]}]

        resp = self.session.post(
            f"{self.target.base_url}{self.target.endpoint}",
            headers=self.target.headers,
            json=payload,
            timeout=self.target.timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        text = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                text = parts[0].get("text", "") or ""
        return UnifiedLLMResponse(text=text, raw=data)


class LLMGateway:
    def __init__(self, registry_path: Optional[Path] = None):
        path = Path(os.getenv("MODEL_REGISTRY_PATH") or registry_path or DEFAULT_REGISTRY_PATH)
        self.registry = _load_registry_cached(str(path))
        self._session = requests.Session()

    def resolve_alias(self, name: str) -> Tuple[str, str]:
        alias_map = {
            "openai-response": ("openai", "openai-response"),
            "openai-chat": ("openai", "openai-chat"),
            "openai-complete": ("openai", "openai-complete"),
            "deepseek-openai": ("deepseek", "openai-chat"),
            "kimi-openai": ("kimi", "openai-chat"),
            "gemini-openai": ("gemini", "gemini-openai"),
            "gemini-native": ("gemini", "gemini-native"),
            "siliconflow-openai": ("siliconflow", "openai-chat"),
        }
        if name in alias_map:
            return alias_map[name]
        if ":" in name:
            parts = name.split(":", 1)
            return parts[0], parts[1]
        defaults = self.registry.get("defaults", {})
        return defaults.get("provider", "openai"), defaults.get("mode", "openai-chat")

    def resolve_target(
        self,
        provider: Optional[str] = None,
        mode: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Target:
        defaults = self.registry.get("defaults", {})

        provider = provider or os.getenv("LLM_PROVIDER") or defaults.get("provider")
        mode = mode or os.getenv("LLM_MODE") or defaults.get("mode")

        if provider and mode and provider in self.registry.get("providers", {}):
            prov_cfg = self.registry["providers"][provider]
        else:
            prov_cfg = self.registry["providers"].get(provider, {})

        mode_cfg = prov_cfg.get("modes", {}).get(mode, {})

        model = model or os.getenv("LLM_MODEL") or os.getenv(mode_cfg.get("model_env", ""))
        if not model:
            model = mode_cfg.get("default_model") or ""
        if not model:
            raise ValueError(f"Model not configured for provider={provider} mode={mode}. Set LLM_MODEL or model_env.")

        base_url = os.getenv(mode_cfg.get("base_url_env", "")) or os.getenv(prov_cfg.get("base_url_env", ""))
        if not base_url:
            base_url = mode_cfg.get("base_url") or prov_cfg.get("base_url") or ""
        if not base_url:
            raise ValueError(f"Base URL not configured for provider={provider} mode={mode}.")

        endpoint = mode_cfg.get("endpoint") or ""
        if not endpoint:
            raise ValueError(f"Endpoint not configured for provider={provider} mode={mode}.")

        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            for env_name in prov_cfg.get("api_key_envs", []):
                val = os.getenv(env_name)
                if val:
                    api_key = val
                    break
        if not api_key:
            raise ValueError(f"API key missing for provider={provider}. Set LLM_API_KEY or {prov_cfg.get('api_key_envs')}")

        headers = self._build_headers(prov_cfg, api_key)

        timeout_sec = _build_timeout_pair(
            default_timeout_sec=defaults.get("timeout_sec", 120),
            timeout_value=os.getenv("LLM_TIMEOUT_SEC"),
            connect_value=os.getenv("LLM_CONNECT_TIMEOUT_SEC"),
            read_value=os.getenv("LLM_READ_TIMEOUT_SEC"),
        )
        retry = int(os.getenv("LLM_RETRY", "")) if os.getenv("LLM_RETRY") else int(defaults.get("retry", 1))

        return Target(
            provider=provider,
            mode=mode,
            model=model,
            base_url=base_url.rstrip("/"),
            endpoint=endpoint,
            headers=headers,
            timeout_sec=timeout_sec,
            retry=retry,
        )

    def _build_headers(self, prov_cfg: Dict[str, Any], api_key: str) -> Dict[str, str]:
        auth = prov_cfg.get("auth", {})
        auth_type = auth.get("type", "bearer")
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if auth_type == "bearer":
            header = auth.get("header", "Authorization")
            prefix = auth.get("prefix", "Bearer ")
            headers[header] = f"{prefix}{api_key}"
        elif auth_type == "x-goog-api-key":
            headers["x-goog-api-key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_adapter(self, target: Target):
        if target.mode == "openai-response":
            return OpenAIResponsesAdapter(target, self._session)
        if target.mode == "openai-complete":
            return OpenAICompletionsAdapter(target, self._session)
        if target.mode == "gemini-native":
            return GeminiNativeAdapter(target, self._session)
        return OpenAIChatAdapter(target, self._session)

    def _target_from_override(
        self,
        override: Dict[str, Any],
        *,
        provider: Optional[str],
        mode: Optional[str],
        model: Optional[str],
    ) -> Target:
        defaults = self.registry.get("defaults", {}) if isinstance(self.registry.get("defaults"), dict) else {}

        provider_final = str(override.get("provider") or provider or "custom").strip() or "custom"
        mode_final = str(override.get("mode") or mode or "openai-chat").strip() or "openai-chat"
        model_final = str(override.get("model") or model or "").strip()
        if not model_final:
            raise ValueError("target_override.model required")

        base_url = str(override.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise ValueError("target_override.base_url required")

        endpoint = str(override.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError("target_override.endpoint required")

        headers_raw = override.get("headers") if isinstance(override.get("headers"), dict) else {}
        headers = {str(k): str(v) for k, v in headers_raw.items() if str(k).strip() and str(v).strip()}
        if not headers:
            api_key = str(override.get("api_key") or "").strip()
            auth_type = str(override.get("auth_type") or "bearer").strip().lower()
            auth_header = str(override.get("auth_header") or "").strip() or (
                "x-goog-api-key" if auth_type == "x-goog-api-key" else "Authorization"
            )
            auth_prefix = str(override.get("auth_prefix") or "Bearer ").strip()
            headers = {"Content-Type": "application/json"}
            if api_key:
                if auth_type == "x-goog-api-key":
                    headers[auth_header] = api_key
                else:
                    headers[auth_header] = f"{auth_prefix}{api_key}"
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        timeout_sec = _build_timeout_pair(
            default_timeout_sec=defaults.get("timeout_sec", 120),
            timeout_value=override.get("timeout_sec"),
            connect_value=override.get("connect_timeout_sec"),
            read_value=override.get("read_timeout_sec"),
        )

        retry_override = override.get("retry")
        if retry_override is None or retry_override == "":
            retry = int(defaults.get("retry", 1))
        else:
            try:
                retry = int(retry_override)
            except Exception:
                retry = int(defaults.get("retry", 1))

        return Target(
            provider=provider_final,
            mode=mode_final,
            model=model_final,
            base_url=base_url,
            endpoint=endpoint,
            headers=headers,
            timeout_sec=timeout_sec,
            retry=max(1, retry),
        )

    def _is_retryable(self, exc: Exception) -> bool:
        # Conservative retry policy: only retry obvious transient failures.
        try:
            import requests as _rq  # local name to avoid shadowing
        except Exception:
            _rq = None

        if _rq is not None:
            if isinstance(exc, (_rq.Timeout, _rq.ConnectionError)):
                return True
            if isinstance(exc, _rq.HTTPError):
                resp = getattr(exc, "response", None)
                code = getattr(resp, "status_code", None)
                if code in {408, 409, 425, 429}:
                    return True
                if isinstance(code, int) and code >= 500:
                    return True
        # Fallback for non-requests errors
        msg = str(exc).lower()
        return any(token in msg for token in ["timeout", "timed out", "temporarily", "rate limit", "429", "503"])

    def generate(
        self,
        req: UnifiedLLMRequest,
        provider: Optional[str] = None,
        mode: Optional[str] = None,
        model: Optional[str] = None,
        allow_fallback: bool = True,
        target_override: Optional[Dict[str, Any]] = None,
    ) -> UnifiedLLMResponse:
        errors: List[Exception] = []
        targets: List[Target] = []

        if isinstance(target_override, dict):
            targets.append(self._target_from_override(target_override, provider=provider, mode=mode, model=model))
        elif provider or mode or model or os.getenv("LLM_PROVIDER") or os.getenv("LLM_MODE") or os.getenv("LLM_MODEL"):
            targets.append(self.resolve_target(provider, mode, model))
        else:
            targets.append(self.resolve_target())

        if allow_fallback:
            for alias in self.registry.get("routing", {}).get("fallback_chain", []):
                prov, mod = self.resolve_alias(alias)
                try:
                    targets.append(self.resolve_target(prov, mod, model))
                except Exception:
                    continue

        seen = set()
        ordered = []
        for t in targets:
            key = (t.provider, t.mode, t.model)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(t)

        for target in ordered:
            adapter = self._build_adapter(target)
            attempts = max(1, int(target.retry or 1))
            for attempt in range(attempts):
                try:
                    return adapter.generate(req)
                except Exception as exc:
                    # Retry transient failures on the same target; otherwise fall back to next target.
                    if attempt < attempts - 1 and self._is_retryable(exc):
                        # bounded exponential backoff with jitter
                        base = 0.25 * (2**attempt)
                        delay = min(4.0, base + random.random() * 0.25)
                        time.sleep(delay)
                        continue
                    errors.append(exc)
                    break
        if errors:
            raise errors[-1]
        raise RuntimeError("No target resolved for LLM request")


__all__ = [
    "UnifiedLLMRequest",
    "UnifiedLLMResponse",
    "LLMGateway",
    "_messages_to_response_input",
]
