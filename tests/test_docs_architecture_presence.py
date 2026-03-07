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
