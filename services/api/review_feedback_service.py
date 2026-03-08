from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Dict, Iterable



def build_review_feedback_summary(*, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    by_action: DefaultDict[str, int] = defaultdict(int)
    by_domain: DefaultDict[str, int] = defaultdict(int)
    by_reason_code: DefaultDict[str, int] = defaultdict(int)
    total_items = 0

    for raw in items:
        item = dict(raw or {})
        total_items += 1

        action = str(item.get('operation') or item.get('action') or '').strip()
        if action:
            by_action[action] += 1

        domain = str(item.get('domain') or '').strip()
        if domain:
            by_domain[domain] += 1

        reason_code = str(item.get('reason_code') or '').strip()
        if reason_code:
            by_reason_code[reason_code] += 1

    return {
        'total_items': total_items,
        'by_action': dict(by_action),
        'by_domain': dict(by_domain),
        'by_reason_code': dict(by_reason_code),
    }
