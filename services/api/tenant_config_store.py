from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    data_dir: str
    uploads_dir: str
    enabled: bool = True
    updated_at: str = ""
    extra: Dict[str, Any] = None  # type: ignore[assignment]

    def normalized(self) -> "TenantConfig":
        extra = self.extra if isinstance(self.extra, dict) else {}
        updated_at = self.updated_at or datetime.now().isoformat(timespec="seconds")
        return TenantConfig(
            tenant_id=str(self.tenant_id),
            data_dir=str(self.data_dir),
            uploads_dir=str(self.uploads_dir),
            enabled=bool(self.enabled),
            updated_at=updated_at,
            extra=extra,
        )


class TenantConfigStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=3.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
            except Exception:
                _log.warning("WAL journal mode not available for %s", self.db_path, exc_info=True)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    data_dir TEXT NOT NULL,
                    uploads_dir TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    extra_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

    def get(self, tenant_id: str) -> Optional[TenantConfig]:
        tid = str(tenant_id or "").strip()
        if not tid:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tenant_id, data_dir, uploads_dir, enabled, updated_at, extra_json FROM tenants WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
        if row is None:
            return None
        extra = {}
        try:
            extra = json.loads(row["extra_json"] or "{}")
        except Exception:
            _log.warning("corrupt extra_json for tenant %s", tid, exc_info=True)
            extra = {}
        return TenantConfig(
            tenant_id=str(row["tenant_id"] or ""),
            data_dir=str(row["data_dir"] or ""),
            uploads_dir=str(row["uploads_dir"] or ""),
            enabled=bool(int(row["enabled"] or 0)),
            updated_at=str(row["updated_at"] or ""),
            extra=extra if isinstance(extra, dict) else {},
        )

    def upsert(self, config: TenantConfig) -> TenantConfig:
        cfg = config.normalized()
        extra_json = json.dumps(cfg.extra or {}, ensure_ascii=False)
        enabled_int = 1 if cfg.enabled else 0
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tenants (tenant_id, data_dir, uploads_dir, enabled, updated_at, extra_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    data_dir=excluded.data_dir,
                    uploads_dir=excluded.uploads_dir,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at,
                    extra_json=excluded.extra_json
                """,
                (cfg.tenant_id, cfg.data_dir, cfg.uploads_dir, enabled_int, cfg.updated_at, extra_json),
            )
        return cfg

    def disable(self, tenant_id: str) -> None:
        tid = str(tenant_id or "").strip()
        if not tid:
            return
        updated_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE tenants SET enabled = 0, updated_at = ? WHERE tenant_id = ?",
                (updated_at, tid),
            )

    def list(self, *, enabled_only: bool = True) -> List[TenantConfig]:
        query = "SELECT tenant_id, data_dir, uploads_dir, enabled, updated_at, extra_json FROM tenants"
        params: tuple = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY tenant_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        out: List[TenantConfig] = []
        for row in rows or []:
            extra = {}
            try:
                extra = json.loads(row["extra_json"] or "{}")
            except Exception:
                _log.warning("corrupt extra_json for tenant %s in list", row["tenant_id"], exc_info=True)
                extra = {}
            out.append(
                TenantConfig(
                    tenant_id=str(row["tenant_id"] or ""),
                    data_dir=str(row["data_dir"] or ""),
                    uploads_dir=str(row["uploads_dir"] or ""),
                    enabled=bool(int(row["enabled"] or 0)),
                    updated_at=str(row["updated_at"] or ""),
                    extra=extra if isinstance(extra, dict) else {},
                )
            )
        return out

