from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def append_review_feedback_row(path: Path, row: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(dict(row or {}), ensure_ascii=False) + '\n')



def read_review_feedback_rows(path: Path) -> List[Dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with target.open('r', encoding='utf-8') as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            item = json.loads(payload)
            if isinstance(item, dict):
                rows.append(item)
    return rows
