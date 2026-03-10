from pathlib import Path


def test_architecture_docs_exist() -> None:
    assert Path('docs/architecture/module-boundaries.md').exists()
    assert Path('docs/architecture/ownership-map.md').exists()


def test_survey_docs_are_indexed() -> None:
    text = Path('docs/INDEX.md').read_text(encoding='utf-8')
    assert 'docs/reference/survey-analysis-contract.md' in text
    assert 'docs/plans/2026-03-06-survey-multi-agent-design.md' in text
    assert 'docs/plans/2026-03-06-survey-multi-agent-implementation-plan.md' in text


def test_survey_contract_doc_covers_runtime_contract_and_rollout_flags() -> None:
    text = Path('docs/reference/survey-analysis-contract.md').read_text(encoding='utf-8')
    assert '/webhooks/surveys/provider' in text
    assert '/teacher/surveys/reports' in text
    assert '/teacher/surveys/review-queue' in text
    assert 'survey_evidence_bundle' in text
    assert 'analysis_artifact' in text
    assert 'SURVEY_ANALYSIS_ENABLED' in text
    assert 'SURVEY_SHADOW_MODE' in text
    assert 'SURVEY_BETA_TEACHER_ALLOWLIST' in text
    assert 'SURVEY_REVIEW_CONFIDENCE_FLOOR' in text


def test_survey_release_checklist_is_indexed_and_actionable() -> None:
    index_text = Path('docs/INDEX.md').read_text(encoding='utf-8')
    assert 'docs/operations/survey-analysis-release-checklist.md' in index_text

    checklist_text = Path('docs/operations/survey-analysis-release-checklist.md').read_text(encoding='utf-8')
    assert '## 5. Shadow 发布清单' in checklist_text
    assert '## 6. Beta 放量清单' in checklist_text
    assert '## 8. 回滚清单' in checklist_text
    assert 'SURVEY_BETA_TEACHER_ALLOWLIST' in checklist_text
    assert 'scripts/survey_bundle_eval.py --fixtures tests/fixtures/surveys --json --summary-only' in checklist_text


def test_multi_domain_analysis_docs_are_indexed_and_actionable() -> None:
    index_text = Path('docs/INDEX.md').read_text(encoding='utf-8')
    assert 'docs/reference/analysis-runtime-contract.md' in index_text
    assert 'docs/operations/multi-domain-analysis-rollout-checklist.md' in index_text
    assert 'docs/plans/2026-03-07-agent-system-bc-evolution-implementation-plan.md' in index_text
    assert 'docs/reference/analysis-domain-onboarding-contract.md' in index_text
    assert 'docs/plans/templates/analysis-domain-extension-template.md' in index_text

    runtime_text = Path('docs/reference/analysis-runtime-contract.md').read_text(encoding='utf-8')
    assert 'target resolver' in runtime_text.lower()
    assert 'artifact adapter' in runtime_text.lower()
    assert 'strategy selector' in runtime_text.lower()
    assert 'specialist runtime' in runtime_text.lower()
    assert 'review queue' in runtime_text.lower()
    assert 'survey' in runtime_text
    assert 'class_report' in runtime_text
    assert 'video_homework' in runtime_text
    assert 'analysis-domain-onboarding-contract.md' in runtime_text

    checklist_text = Path('docs/operations/multi-domain-analysis-rollout-checklist.md').read_text(encoding='utf-8')
    assert '## 5. Shadow 发布清单' in checklist_text
    assert '## 6. Beta 放量清单' in checklist_text
    assert '## 7. 正式放量清单' in checklist_text
    assert '## 8. 回滚清单' in checklist_text
    assert 'scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only' in checklist_text


def test_survey_contract_doc_links_to_unified_analysis_runtime() -> None:
    text = Path('docs/reference/survey-analysis-contract.md').read_text(encoding='utf-8')
    assert 'docs/reference/analysis-runtime-contract.md' in text
    assert '统一 analysis report plane' in text
