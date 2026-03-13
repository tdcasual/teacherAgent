from __future__ import annotations

import pytest

from services.api.artifacts.contracts import ArtifactEnvelope
from services.api.artifacts.registry import (
    ArtifactAdapterNotFoundError,
    ArtifactAdapterRegistry,
    ArtifactAdapterSpec,
)
from services.api.artifacts.runtime import ArtifactAdapterRuntime
from services.api.wiring.survey_wiring import build_survey_artifact_registry


def test_registry_registers_and_queries_artifact_adapters() -> None:
    registry = ArtifactAdapterRegistry()
    registry.register(
        ArtifactAdapterSpec(
            adapter_id='survey.structured.bundle',
            accepted_inputs=['survey_payload'],
            output_artifact_type='survey_evidence_bundle',
            task_kinds=['survey.analysis'],
            validation_rules=['teacher_id_required'],
        ),
        adapter=lambda payload, _context=None: ArtifactEnvelope(
            artifact_type='survey_evidence_bundle',
            schema_version='v1',
            subject_scope={'teacher_id': payload['teacher_id']},
            evidence_refs=[],
            confidence=1.0,
            missing_fields=[],
            provenance={'source': 'structured'},
            payload=payload,
        ),
    )

    spec = registry.get('survey.structured.bundle')
    matches = registry.find(output_artifact_type='survey_evidence_bundle')

    assert spec.output_artifact_type == 'survey_evidence_bundle'
    assert [item.adapter_id for item in matches] == ['survey.structured.bundle']



def test_runtime_runs_registered_adapter_for_input_type_and_task_kind() -> None:
    registry = ArtifactAdapterRegistry()
    registry.register(
        ArtifactAdapterSpec(
            adapter_id='survey.structured.bundle',
            accepted_inputs=['survey_payload'],
            output_artifact_type='survey_evidence_bundle',
            task_kinds=['survey.analysis'],
            validation_rules=['teacher_id_required'],
        ),
        adapter=lambda payload, _context=None: ArtifactEnvelope(
            artifact_type='survey_evidence_bundle',
            schema_version='v1',
            subject_scope={'teacher_id': payload['teacher_id']},
            evidence_refs=[],
            confidence=1.0,
            missing_fields=[],
            provenance={'source': 'structured'},
            payload=payload,
        ),
    )
    runtime = ArtifactAdapterRuntime(registry)

    artifact = runtime.run(input_type='survey_payload', task_kind='survey.analysis', payload={'teacher_id': 'teacher_1'})

    assert artifact.artifact_type == 'survey_evidence_bundle'
    assert artifact.subject_scope['teacher_id'] == 'teacher_1'



def test_runtime_raises_for_unknown_adapter_resolution() -> None:
    runtime = ArtifactAdapterRuntime(ArtifactAdapterRegistry())

    with pytest.raises(ArtifactAdapterNotFoundError):
        runtime.run(input_type='unknown_payload', task_kind='survey.analysis', payload={})



def test_survey_wiring_registers_survey_artifact_adapter() -> None:
    registry = build_survey_artifact_registry(object())

    spec = registry.get('survey.bundle.adapter')

    assert spec.output_artifact_type == 'survey_evidence_bundle'
    assert spec.accepted_inputs == ['survey_bundle']
