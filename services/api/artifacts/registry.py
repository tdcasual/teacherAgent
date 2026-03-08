from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from .contracts import ArtifactEnvelope

ArtifactAdapter = Callable[[Dict[str, Any], Optional[Dict[str, Any]]], ArtifactEnvelope | Dict[str, Any]]


class ArtifactAdapterNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class ArtifactAdapterSpec:
    adapter_id: str
    accepted_inputs: List[str] = field(default_factory=list)
    output_artifact_type: str = ''
    task_kinds: List[str] = field(default_factory=list)
    validation_rules: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegisteredArtifactAdapter:
    spec: ArtifactAdapterSpec
    adapter: ArtifactAdapter


class ArtifactAdapterRegistry:
    def __init__(self) -> None:
        self._entries: Dict[str, RegisteredArtifactAdapter] = {}

    def register(self, spec: ArtifactAdapterSpec, *, adapter: ArtifactAdapter) -> None:
        self._entries[spec.adapter_id] = RegisteredArtifactAdapter(spec=spec, adapter=adapter)

    def get(self, adapter_id: str) -> ArtifactAdapterSpec:
        return self.get_entry(adapter_id).spec

    def get_entry(self, adapter_id: str) -> RegisteredArtifactAdapter:
        entry = self._entries.get(str(adapter_id or '').strip())
        if entry is None:
            raise ArtifactAdapterNotFoundError(str(adapter_id or ''))
        return entry

    def find(self, *, output_artifact_type: str) -> List[ArtifactAdapterSpec]:
        output_artifact_type_final = str(output_artifact_type or '').strip()
        matches = [
            entry.spec
            for entry in self._entries.values()
            if entry.spec.output_artifact_type == output_artifact_type_final
        ]
        matches.sort(key=lambda item: item.adapter_id)
        return matches

    def resolve(
        self,
        *,
        input_type: str,
        task_kind: str,
        adapter_id: Optional[str] = None,
    ) -> RegisteredArtifactAdapter:
        adapter_id_final = str(adapter_id or '').strip()
        if adapter_id_final:
            return self.get_entry(adapter_id_final)

        input_type_final = str(input_type or '').strip()
        task_kind_final = str(task_kind or '').strip()
        for entry in sorted(self._entries.values(), key=lambda item: item.spec.adapter_id):
            if input_type_final not in entry.spec.accepted_inputs:
                continue
            if task_kind_final not in entry.spec.task_kinds:
                continue
            return entry
        raise ArtifactAdapterNotFoundError(f'{input_type_final}:{task_kind_final}')



def _default_adapter_lookup() -> Dict[str, ArtifactAdapter]:
    from ..report_adapters import (
        adapt_pdf_report_summary,
        adapt_self_hosted_form_json,
        adapt_web_export_html,
    )
    from ..survey_bundle_models import SurveyEvidenceBundle

    return {
        'survey.bundle.adapter': lambda payload, _context=None: SurveyEvidenceBundle.model_validate(payload).to_artifact_envelope(),
        'class_report.self_hosted_form.adapter': adapt_self_hosted_form_json,
        'class_report.web_export.adapter': adapt_web_export_html,
        'class_report.pdf_summary.adapter': adapt_pdf_report_summary,
    }



def build_artifact_registry_from_manifests(manifests: Iterable[Any]) -> ArtifactAdapterRegistry:
    registry = ArtifactAdapterRegistry()
    adapter_lookup = _default_adapter_lookup()
    for manifest in manifests:
        for spec in list(getattr(manifest, 'artifact_adapters', []) or []):
            adapter = adapter_lookup.get(spec.adapter_id)
            if adapter is None:
                raise ArtifactAdapterNotFoundError(spec.adapter_id)
            registry.register(spec, adapter=adapter)
    return registry



def build_platform_artifact_registry(core: Any | None = None, *, manifest_registry: Any | None = None) -> ArtifactAdapterRegistry:
    del core
    if manifest_registry is None:
        from ..domains.manifest_registry import build_default_domain_manifest_registry

        manifest_registry = build_default_domain_manifest_registry()
    return build_artifact_registry_from_manifests(manifest_registry.list())
