from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

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



def build_platform_artifact_registry(core: Any | None = None) -> ArtifactAdapterRegistry:
    del core
    from ..report_adapters import (
        adapt_pdf_report_summary,
        adapt_self_hosted_form_json,
        adapt_web_export_html,
    )
    from ..survey_bundle_models import SurveyEvidenceBundle

    registry = ArtifactAdapterRegistry()
    registry.register(
        ArtifactAdapterSpec(
            adapter_id='survey.bundle.adapter',
            accepted_inputs=['survey_bundle'],
            output_artifact_type='survey_evidence_bundle',
            task_kinds=['survey.analysis', 'survey.chat_followup'],
            validation_rules=[],
        ),
        adapter=lambda payload, _context=None: SurveyEvidenceBundle.model_validate(payload).to_artifact_envelope(),
    )
    registry.register(
        ArtifactAdapterSpec(
            adapter_id='class_report.self_hosted_form.adapter',
            accepted_inputs=['self_hosted_form_json'],
            output_artifact_type='class_signal_bundle',
            task_kinds=['class_report.analysis'],
            validation_rules=['teacher_id_required'],
        ),
        adapter=adapt_self_hosted_form_json,
    )
    registry.register(
        ArtifactAdapterSpec(
            adapter_id='class_report.web_export.adapter',
            accepted_inputs=['web_export_html'],
            output_artifact_type='class_signal_bundle',
            task_kinds=['class_report.analysis'],
            validation_rules=['teacher_id_required'],
        ),
        adapter=adapt_web_export_html,
    )
    registry.register(
        ArtifactAdapterSpec(
            adapter_id='class_report.pdf_summary.adapter',
            accepted_inputs=['pdf_report_summary'],
            output_artifact_type='class_signal_bundle',
            task_kinds=['class_report.analysis'],
            validation_rules=['teacher_id_required'],
        ),
        adapter=adapt_pdf_report_summary,
    )
    return registry
