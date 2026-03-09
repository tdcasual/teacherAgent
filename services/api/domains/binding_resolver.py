from __future__ import annotations

from typing import Any, TypeVar


ResolvedBinding = TypeVar('ResolvedBinding')


def resolve_manifest_binding(
    binding: Any,
    *,
    lookup: dict[str, ResolvedBinding],
    domain_id: str,
    label: str,
) -> ResolvedBinding:
    if callable(binding):
        return binding
    binding_name = str(binding or '').strip()
    if not binding_name:
        raise ValueError(f'invalid {label} for domain {domain_id}')
    resolved = lookup.get(binding_name)
    if resolved is None:
        raise ValueError(f'invalid {label} for domain {domain_id}')
    return resolved
