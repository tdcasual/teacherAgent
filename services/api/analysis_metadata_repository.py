from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol

from .job_repository import _atomic_write_json


class AnalysisMetadataRepository(Protocol):
    def read_json(self, relative_path: str) -> Dict[str, Any]: ...
    def write_json(self, relative_path: str, payload: Dict[str, Any]) -> Path: ...
    def read_jsonl(self, relative_path: str) -> List[Dict[str, Any]]: ...
    def append_jsonl(self, relative_path: str, item: Dict[str, Any]) -> Path: ...


@dataclass(frozen=True)
class FileBackedAnalysisMetadataRepository:
    base_dir: Path

    def read_json(self, relative_path: str) -> Dict[str, Any]:
        target = self._resolve(relative_path)
        payload = json.loads(target.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}

    def write_json(self, relative_path: str, payload: Dict[str, Any]) -> Path:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(target, payload)
        return target

    def read_jsonl(self, relative_path: str) -> List[Dict[str, Any]]:
        target = self._resolve(relative_path)
        if not target.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in target.read_text(encoding='utf-8').splitlines():
            raw = line.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def append_jsonl(self, relative_path: str, item: Dict[str, Any]) -> Path:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + '\n')
        return target

    def _resolve(self, relative_path: str) -> Path:
        return self.base_dir / str(relative_path or '').strip()
