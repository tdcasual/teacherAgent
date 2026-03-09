from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class AnalysisMetricsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load_snapshot(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}

    def save_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return snapshot
