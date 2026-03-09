from __future__ import annotations

from typing import Any, Dict

_REQUIRED_LINEAGE_FIELDS = (
    'strategy_id',
    'strategy_version',
    'prompt_version',
    'adapter_version',
    'runtime_version',
)


def extract_analysis_lineage(payload: Dict[str, Any], *, strict: bool = False) -> Dict[str, str]:
    raw = dict(payload or {})
    missing = [field for field in _REQUIRED_LINEAGE_FIELDS if not str(raw.get(field) or '').strip()]
    if strict and missing:
        raise ValueError(f"analysis lineage missing required fields: {', '.join(missing)}")
    strategy_id = str(raw.get('strategy_id') or '').strip()
    return {
        'strategy_id': strategy_id,
        'strategy_version': str(raw.get('strategy_version') or 'v1').strip() or 'v1',
        'prompt_version': str(raw.get('prompt_version') or 'v1').strip() or 'v1',
        'adapter_version': str(raw.get('adapter_version') or 'v1').strip() or 'v1',
        'runtime_version': str(raw.get('runtime_version') or 'v1').strip() or 'v1',
    }
