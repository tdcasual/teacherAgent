#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.review_feedback_service import build_review_feedback_dataset  # noqa: E402


def _load_items(path: Path) -> List[Dict[str, Any]]:
    if path.suffix == '.jsonl':
        items: List[Dict[str, Any]] = []
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(payload)
        return items

    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, dict) and isinstance(payload.get('items'), list):
        return [dict(item or {}) for item in payload.get('items') or [] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [dict(item or {}) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [dict(payload)]
    raise ValueError(f'unsupported feedback payload: {path}')



def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export review queue outcomes into a normalized feedback dataset.')
    parser.add_argument('--input', required=True, help='input JSON or JSONL review feedback payload')
    parser.add_argument('--output', default='', help='optional output file path, defaults to stdout')
    args = parser.parse_args(argv)

    dataset = build_review_feedback_dataset(items=_load_items(Path(args.input)))
    rendered = json.dumps(dataset, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
