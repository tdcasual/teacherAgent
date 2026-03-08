from __future__ import annotations

from services.api.artifacts.registry import build_platform_artifact_registry
from services.api.domains.manifest_registry import build_default_domain_manifest_registry
from services.api.strategies.selector import build_default_strategy_selector
from services.api.wiring.survey_wiring import (
    build_class_report_specialist_registry,
    build_multimodal_specialist_registry,
    build_survey_specialist_registry,
)



def test_default_domain_manifest_registry_exposes_supported_domains_and_rollout_flags() -> None:
    registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)

    manifests = registry.list()
    assert [item.domain_id for item in manifests] == ['class_report', 'survey', 'video_homework']

    survey = registry.get('survey')
    class_report = registry.get('class_report')
    video_homework = registry.get('video_homework')

    assert {item.strategy_id for item in survey.strategies} == {
        'survey.teacher.report',
        'survey.chat.followup',
    }
    assert survey.feature_flags == ['SURVEY_ANALYSIS_ENABLED', 'SURVEY_SHADOW_MODE', 'SURVEY_BETA_TEACHER_ALLOWLIST']
    assert class_report.feature_flags == []
    assert video_homework.feature_flags == [
        'MULTIMODAL_ENABLED',
        'MULTIMODAL_MAX_UPLOAD_BYTES',
        'MULTIMODAL_MAX_DURATION_SEC',
        'MULTIMODAL_EXTRACT_TIMEOUT_SEC',
    ]



def test_platform_artifact_registry_matches_manifest_declarations() -> None:
    manifest_registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)
    runtime_registry = build_platform_artifact_registry(manifest_registry=manifest_registry)

    declared_adapter_ids = {
        spec.adapter_id
        for manifest in manifest_registry.list()
        for spec in manifest.artifact_adapters
    }

    assert declared_adapter_ids == {
        'survey.bundle.adapter',
        'class_report.self_hosted_form.adapter',
        'class_report.web_export.adapter',
        'class_report.pdf_summary.adapter',
    }
    assert runtime_registry.get('survey.bundle.adapter').output_artifact_type == 'survey_evidence_bundle'
    assert [item.adapter_id for item in runtime_registry.find(output_artifact_type='class_signal_bundle')] == [
        'class_report.pdf_summary.adapter',
        'class_report.self_hosted_form.adapter',
        'class_report.web_export.adapter',
    ]



def test_default_strategy_selector_uses_manifest_declared_specs() -> None:
    manifest_registry = build_default_domain_manifest_registry(review_confidence_floor=0.66)
    selector = build_default_strategy_selector(
        review_confidence_floor=0.66,
        manifest_registry=manifest_registry,
    )

    manifest_strategy_ids = {
        spec.strategy_id
        for manifest in manifest_registry.list()
        for spec in manifest.strategies
    }
    selector_strategy_ids = {spec.strategy_id for spec in selector._specs}

    assert selector_strategy_ids == manifest_strategy_ids
    assert next(spec for spec in selector._specs if spec.strategy_id == 'survey.teacher.report').confidence_floor == 0.66
    assert next(spec for spec in selector._specs if spec.strategy_id == 'video_homework.teacher.report').specialist_agent == 'video_homework_analyst'



def test_specialist_registries_reuse_manifest_specs() -> None:
    manifest_registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)

    survey_manifest = manifest_registry.get('survey')
    class_report_manifest = manifest_registry.get('class_report')
    video_homework_manifest = manifest_registry.get('video_homework')

    assert build_survey_specialist_registry(object()).get('survey_analyst') == survey_manifest.specialists[0]
    assert build_class_report_specialist_registry(object()).get('class_signal_analyst') == class_report_manifest.specialists[0]
    assert build_multimodal_specialist_registry(object()).get('video_homework_analyst') == video_homework_manifest.specialists[0]
