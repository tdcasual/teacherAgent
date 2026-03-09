from __future__ import annotations

from pathlib import Path

import pytest

from services.api.analysis_report_service import (
    AnalysisReportProvider,
    build_analysis_report_deps,
    get_analysis_report,
    list_analysis_reports,
    list_analysis_review_queue,
    rerun_analysis_report,
)
from services.api.domains.manifest_models import DomainManifest, DomainReportBinding
from services.api.domains.manifest_registry import (
    DomainManifestRegistry,
    build_default_domain_manifest_registry,
)
from services.api.job_repository import write_survey_job
from services.api.survey_repository import (
    append_survey_review_queue_item,
    write_survey_bundle,
    write_survey_report,
)


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'



def _seed_survey_report(core: _Core) -> None:
    write_survey_report(
        'report_1',
        {
            'report_id': 'report_1',
            'job_id': 'job_1',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'analysis_ready',
            'confidence': 0.41,
            'summary': '结论可信度偏低，需要复核',
            'analysis_artifact': {'executive_summary': '结论可信度偏低，需要复核'},
            'bundle_meta': {'parse_confidence': 0.41, 'missing_fields': ['question_summaries']},
            'created_at': '2026-03-06T10:00:00',
            'updated_at': '2026-03-06T10:05:00',
        },
        core=core,
    )
    write_survey_bundle(
        'job_1',
        {
            'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider', 'submission_id': 'sub-1'},
            'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
            'question_summaries': [],
            'group_breakdowns': [],
            'free_text_signals': [],
            'attachments': [],
            'parse_confidence': 0.41,
            'missing_fields': ['question_summaries'],
            'provenance': {'source': 'unstructured'},
        },
        core=core,
    )
    append_survey_review_queue_item(
        {'report_id': 'report_1', 'teacher_id': 'teacher_1', 'reason': 'low_confidence', 'confidence': 0.41},
        core=core,
    )
    write_survey_job(
        'job_pending_1',
        {
            'job_id': 'job_pending_1',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'bundle_ready',
            'queue_status': 'queued',
            'created_at': '2026-03-06T09:00:00',
        },
        core=core,
    )
    write_survey_bundle(
        'job_pending_1',
        {
            'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider', 'submission_id': 'sub-2'},
            'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
            'question_summaries': [],
            'group_breakdowns': [],
            'free_text_signals': [],
            'attachments': [],
            'parse_confidence': 0.58,
            'missing_fields': ['question_summaries'],
            'provenance': {'source': 'structured'},
        },
        core=core,
    )



def test_list_analysis_reports_filters_survey_reports_on_unified_plane(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    _seed_survey_report(core)

    deps = build_analysis_report_deps(core)
    result = list_analysis_reports(
        teacher_id='teacher_1',
        domain='survey',
        status='analysis_ready',
        strategy_id='survey.teacher.report',
        target_type='report',
        deps=deps,
    )

    assert [item['report_id'] for item in result['items']] == ['report_1']
    assert result['items'][0]['analysis_type'] == 'survey'
    assert result['items'][0]['target_type'] == 'report'
    assert result['items'][0]['target_id'] == 'report_1'
    assert result['items'][0]['strategy_id'] == 'survey.teacher.report'
    assert result['items'][0]['review_required'] is True



def test_get_and_rerun_analysis_report_bridge_to_survey_provider(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    _seed_survey_report(core)

    deps = build_analysis_report_deps(core)
    detail = get_analysis_report(report_id='report_1', teacher_id='teacher_1', domain='survey', deps=deps)
    rerun = rerun_analysis_report(report_id='report_1', teacher_id='teacher_1', domain='survey', reason='refresh', deps=deps)

    assert detail['report']['analysis_type'] == 'survey'
    assert detail['report']['strategy_id'] == 'survey.teacher.report'
    assert detail['artifact_meta']['parse_confidence'] == 0.41
    assert detail['replay_context']['lineage']['runtime_version'] == 'v1'
    assert detail['replay_context']['artifact_payload']['survey_meta']['title'] == '课堂反馈问卷'
    assert detail['replay_context']['strategy_target']['strategy_id'] == 'survey.teacher.report'
    assert rerun['status'] == 'rerun_requested'
    assert rerun['domain'] == 'survey'



def test_list_analysis_review_queue_filters_by_domain() -> None:
    deps = build_analysis_report_deps(object())
    deps = deps.__class__(
        providers=deps.providers,
        now_iso=deps.now_iso,
        list_review_queue=lambda teacher_id, domain=None, status=None: {
            'items': [
                {
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'report_id': 'report_1',
                    'teacher_id': 'teacher_1',
                    'status': 'queued',
                    'reason': 'low_confidence',
                },
                {
                    'item_id': 'rvw_2',
                    'domain': 'class_report',
                    'report_id': 'report_9',
                    'teacher_id': 'teacher_1',
                    'status': 'queued',
                    'reason': 'needs_review',
                },
            ]
        },
    )

    result = list_analysis_review_queue(teacher_id='teacher_1', domain='survey', status='queued', deps=deps)

    assert result['items'] == [
        {
            'item_id': 'rvw_1',
            'domain': 'survey',
            'report_id': 'report_1',
            'teacher_id': 'teacher_1',
            'status': 'queued',
            'reason': 'low_confidence',
        }
    ]


def test_list_analysis_reports_supports_video_homework_domain(tmp_path: Path) -> None:
    from services.api.multimodal_report_service import (
        build_multimodal_report_deps,
        write_multimodal_report,
    )

    core = _Core(tmp_path)
    multimodal_deps = build_multimodal_report_deps(core)
    write_multimodal_report(
        'submission_1',
        {
            'report_id': 'submission_1',
            'submission_id': 'submission_1',
            'teacher_id': 'teacher_1',
            'analysis_type': 'video_homework',
            'target_type': 'submission',
            'target_id': 'submission_1',
            'strategy_id': 'video_homework.teacher.report',
            'status': 'analysis_ready',
            'confidence': 0.86,
            'summary': '学生能完整展示实验步骤。',
            'analysis_artifact': {'executive_summary': '学生能完整展示实验步骤。'},
            'artifact_meta': {'student_id': 'student_1', 'parse_confidence': 0.84},
        },
        deps=multimodal_deps,
    )

    deps = build_analysis_report_deps(core)
    result = list_analysis_reports(
        teacher_id='teacher_1',
        domain='video_homework',
        status='analysis_ready',
        strategy_id='video_homework.teacher.report',
        target_type='submission',
        deps=deps,
    )

    assert [item['report_id'] for item in result['items']] == ['submission_1']
    assert result['items'][0]['analysis_type'] == 'video_homework'
    assert result['items'][0]['target_type'] == 'submission'


def test_list_analysis_review_queue_returns_summary_and_unresolved_filter() -> None:
    deps = build_analysis_report_deps(object())
    deps = deps.__class__(
        providers=deps.providers,
        now_iso=deps.now_iso,
        list_review_queue=lambda teacher_id, domain=None, status=None: {
            'items': [
                {
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'report_id': 'report_1',
                    'teacher_id': 'teacher_1',
                    'status': 'queued',
                    'reason': 'low_confidence_bundle',
                    'reason_code': 'low_confidence',
                    'disposition': 'open',
                },
                {
                    'item_id': 'rvw_2',
                    'domain': 'class_report',
                    'report_id': 'report_9',
                    'teacher_id': 'teacher_1',
                    'status': 'dismissed',
                    'reason': 'missing_fields',
                    'reason_code': 'missing_fields',
                    'disposition': 'dismissed',
                },
            ],
            'summary': {
                'total_items': 2,
                'unresolved_items': 1,
                'reason_counts': {'low_confidence': 1, 'missing_fields': 1},
                'domains': [
                    {'domain': 'class_report', 'total_items': 1, 'unresolved_items': 0},
                    {'domain': 'survey', 'total_items': 1, 'unresolved_items': 1},
                ],
            },
        },
    )

    result = list_analysis_review_queue(teacher_id='teacher_1', domain=None, status='unresolved', deps=deps)

    assert [item['item_id'] for item in result['items']] == ['rvw_1']
    assert result['summary']['unresolved_items'] == 1
    assert result['summary']['reason_counts']['low_confidence'] == 1



def test_build_analysis_report_deps_uses_manifest_registry_subset(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    registry = DomainManifestRegistry()
    default_registry = build_default_domain_manifest_registry(review_confidence_floor=0.65)
    registry.register(default_registry.get('survey'))

    deps = build_analysis_report_deps(core, manifest_registry=registry)

    assert sorted(deps.providers.keys()) == ['survey']



def test_build_analysis_report_deps_requires_report_binding_metadata() -> None:
    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='broken',
            display_name='Broken',
            report_binding=DomainReportBinding(provider_factory=''),
        )
    )

    with pytest.raises(ValueError, match='report binding'):
        build_analysis_report_deps(object(), manifest_registry=registry)



def test_rerun_analysis_report_returns_previous_lineage(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    _seed_survey_report(core)

    deps = build_analysis_report_deps(core)
    rerun = rerun_analysis_report(
        report_id='report_1',
        teacher_id='teacher_1',
        domain='survey',
        reason='refresh',
        deps=deps,
    )
    detail = get_analysis_report(report_id='report_1', teacher_id='teacher_1', domain='survey', deps=deps)

    assert rerun['previous_lineage']['strategy_version'] == 'v1'
    assert rerun['previous_lineage']['prompt_version'] == 'v1'
    assert rerun['previous_lineage']['adapter_version'] == 'v1'
    assert rerun['previous_lineage']['runtime_version'] == 'v1'
    assert rerun['current_lineage']['strategy_version'] == 'v1'
    assert rerun['current_lineage']['prompt_version'] == 'v1'
    assert rerun['current_lineage']['adapter_version'] == 'v1'
    assert rerun['current_lineage']['runtime_version'] == 'v1'
    assert detail['artifact_meta']['rerun_base_lineage']['runtime_version'] == 'v1'



def _build_callable_report_provider(_core: object | None = None) -> AnalysisReportProvider:
    return AnalysisReportProvider(
        domain='callable',
        default_strategy_id='callable.teacher.report',
        now_iso=lambda: '2026-03-09T00:00:00',
        list_reports=lambda teacher_id, status=None: {'items': []},
        get_report=lambda report_id, teacher_id: {'report_id': report_id, 'teacher_id': teacher_id},
        rerun_report=lambda report_id, teacher_id, reason=None: {'report_id': report_id, 'teacher_id': teacher_id, 'reason': reason},
        list_review_queue=lambda teacher_id: {
            'items': [],
            'summary': {'total_items': 0, 'unresolved_items': 0, 'reason_counts': {}, 'domains': []},
        },
        operate_review_queue_item=lambda item_id, action, reviewer_id, operator_note=None: {
            'item_id': item_id,
            'action': action,
            'reviewer_id': reviewer_id,
            'operator_note': operator_note,
        },
    )


def test_build_analysis_report_deps_supports_callable_provider_binding(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='callable',
            display_name='Callable Reports',
            report_binding=DomainReportBinding(provider_factory=_build_callable_report_provider),
        )
    )

    deps = build_analysis_report_deps(core, manifest_registry=registry)

    assert sorted(deps.providers.keys()) == ['callable']



def _build_shared_report_provider(_core: object | None = None) -> AnalysisReportProvider:
    return AnalysisReportProvider(
        domain='shared',
        default_strategy_id='shared.teacher.report',
        now_iso=lambda: '2026-03-09T10:00:00',
        list_reports=lambda teacher_id, status=None: {'items': []},
        get_report=lambda report_id, teacher_id: {'report': {'report_id': report_id, 'teacher_id': teacher_id}},
        rerun_report=lambda report_id, teacher_id, reason=None: {'report_id': report_id, 'teacher_id': teacher_id, 'reason': reason},
        list_review_queue=lambda teacher_id: {'items': []},
        operate_review_queue_item=lambda item_id, action, reviewer_id, operator_note=None: {'item_id': item_id, 'action': action},
    )


def _build_mismatched_report_provider(_core: object | None = None) -> AnalysisReportProvider:
    return AnalysisReportProvider(
        domain='other-domain',
        default_strategy_id='shared.teacher.report',
        now_iso=lambda: '2026-03-09T10:00:00',
        list_reports=lambda teacher_id, status=None: {'items': []},
        get_report=lambda report_id, teacher_id: {'report': {'report_id': report_id, 'teacher_id': teacher_id}},
        rerun_report=lambda report_id, teacher_id, reason=None: {'report_id': report_id, 'teacher_id': teacher_id, 'reason': reason},
        list_review_queue=lambda teacher_id: {'items': []},
        operate_review_queue_item=lambda item_id, action, reviewer_id, operator_note=None: {'item_id': item_id, 'action': action},
    )


def test_build_analysis_report_deps_uses_shared_binding_registry(monkeypatch, tmp_path: Path) -> None:
    from services.api.domains import binding_registry
    from services.api.domains.manifest_models import DomainManifest, DomainReportBinding
    from services.api.domains.manifest_registry import DomainManifestRegistry
    from services.api.strategies.contracts import StrategySpec

    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='shared',
            display_name='Shared',
            strategies=[
                StrategySpec(
                    strategy_id='shared.teacher.report',
                    accepted_artifacts=['shared_artifact'],
                    task_kinds=['shared.analysis'],
                    specialist_agent='shared_analyst',
                    roles=['teacher'],
                )
            ],
            report_binding=DomainReportBinding(provider_factory='shared_provider'),
        )
    )

    monkeypatch.setattr(binding_registry, 'report_provider_factory_lookup', lambda: {'shared_provider': _build_shared_report_provider})

    deps = build_analysis_report_deps(_Core(tmp_path), manifest_registry=registry)

    assert sorted(deps.providers.keys()) == ['shared']


def test_build_analysis_report_deps_rejects_provider_domain_mismatch(tmp_path: Path) -> None:
    from services.api.domains.manifest_models import DomainManifest, DomainReportBinding
    from services.api.domains.manifest_registry import DomainManifestRegistry
    from services.api.strategies.contracts import StrategySpec

    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='shared',
            display_name='Shared',
            strategies=[
                StrategySpec(
                    strategy_id='shared.teacher.report',
                    accepted_artifacts=['shared_artifact'],
                    task_kinds=['shared.analysis'],
                    specialist_agent='shared_analyst',
                    roles=['teacher'],
                )
            ],
            report_binding=DomainReportBinding(provider_factory=_build_mismatched_report_provider),
        )
    )

    with pytest.raises(ValueError, match='report binding'):
        build_analysis_report_deps(_Core(tmp_path), manifest_registry=registry)
