from __future__ import annotations

from typing import Any, Dict, Optional

from .contracts import ArtifactEnvelope
from .registry import ArtifactAdapterRegistry


class ArtifactAdapterRuntime:
    def __init__(self, registry: ArtifactAdapterRegistry) -> None:
        self.registry = registry

    def run(
        self,
        *,
        input_type: str,
        task_kind: str,
        payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        adapter_id: Optional[str] = None,
    ) -> ArtifactEnvelope:
        entry = self.registry.resolve(input_type=input_type, task_kind=task_kind, adapter_id=adapter_id)
        _validate_payload(payload, entry.spec.validation_rules)
        result = entry.adapter(dict(payload or {}), dict(context or {}))
        return ArtifactEnvelope.model_validate(result)



def _validate_payload(payload: Dict[str, Any], validation_rules: list[str]) -> None:
    for rule in validation_rules:
        if rule == 'teacher_id_required':
            teacher_id = str(payload.get('teacher_id') or (payload.get('audience_scope') or {}).get('teacher_id') or '').strip()
            if not teacher_id:
                raise ValueError('teacher_id_required')
