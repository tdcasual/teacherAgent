from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .tenant_app_factory import TenantAppInstance, TenantLimits, TenantSettings, create_tenant_app
from .tenant_config_store import TenantConfigStore

_log = logging.getLogger(__name__)


_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_tenant_id(value: Any) -> str:
    tid = str(value or "").strip()
    if not tid or not _TENANT_ID_RE.fullmatch(tid):
        raise ValueError("invalid tenant_id")
    return tid


@dataclass
class TenantHandle:
    tenant_id: str
    settings: TenantSettings
    instance: TenantAppInstance

    @property
    def app(self):
        return self.instance.app


class TenantRegistry:
    def __init__(self, store: TenantConfigStore):
        self.store = store
        self._lock = threading.RLock()
        self._handles: Dict[str, TenantHandle] = {}

    def get_loaded(self, tenant_id: str) -> Optional[TenantHandle]:
        with self._lock:
            return self._handles.get(tenant_id)

    def get_or_create(self, tenant_id: str) -> TenantHandle:
        tid = validate_tenant_id(tenant_id)
        with self._lock:
            existing = self._handles.get(tid)
            if existing is not None:
                return existing

            cfg = self.store.get(tid)
            if cfg is None or not cfg.enabled:
                raise KeyError("tenant_not_found")

            limits = TenantLimits()
            extra = cfg.extra if isinstance(cfg.extra, dict) else {}
            limits_raw = extra.get("limits") if isinstance(extra.get("limits"), dict) else {}
            for key in ("llm_total", "llm_student", "llm_teacher", "ocr"):
                raw = limits_raw.get(key) if isinstance(limits_raw, dict) else None
                if raw is None:
                    raw = extra.get(key)
                if raw is None:
                    continue
                try:
                    value = int(raw)
                except Exception:
                    continue
                if value <= 0:
                    continue
                limits = TenantLimits(**{**limits.__dict__, key: value})

            settings = TenantSettings(
                tenant_id=tid,
                data_dir=Path(cfg.data_dir).expanduser().resolve(),
                uploads_dir=Path(cfg.uploads_dir).expanduser().resolve(),
                limits=limits,
            )
            instance = create_tenant_app(settings)
            try:
                instance.startup()
            except Exception:
                _log.error("tenant %s startup failed", tid, exc_info=True)
                raise
            handle = TenantHandle(tenant_id=tid, settings=settings, instance=instance)
            self._handles[tid] = handle
            return handle

    def replace(self, tenant_id: str) -> TenantHandle:
        tid = validate_tenant_id(tenant_id)
        with self._lock:
            prior = self._handles.pop(tid, None)
        if prior is not None:
            try:
                prior.instance.shutdown()
            except Exception:
                _log.warning("shutdown failed for tenant %s during replace", tid, exc_info=True)
        return self.get_or_create(tid)

    def unload(self, tenant_id: str) -> None:
        tid = validate_tenant_id(tenant_id)
        with self._lock:
            prior = self._handles.pop(tid, None)
        if prior is not None:
            try:
                prior.instance.shutdown()
            except Exception:
                _log.warning("shutdown failed for tenant %s during unload", tid, exc_info=True)
