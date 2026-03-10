from __future__ import annotations

from pathlib import Path


def test_module_boundaries_avoids_removed_student_shell_paths() -> None:
    doc = Path('docs/architecture/module-boundaries.md').read_text(encoding='utf-8')
    outdated_paths = [
        'frontend/apps/student/src/features/session/StudentSessionShell.tsx',
        'frontend/apps/student/src/features/chat/StudentChatPanel.tsx',
        'frontend/apps/student/src/features/workbench/StudentWorkbench.tsx',
    ]
    for path in outdated_paths:
        assert path not in doc, f'outdated path remains in architecture doc: {path}'



def test_analysis_domain_onboarding_docs_are_indexed_and_actionable() -> None:
    index_text = Path('docs/INDEX.md').read_text(encoding='utf-8')
    assert 'docs/reference/analysis-domain-onboarding-template.md' in index_text
    assert 'docs/reference/analysis-domain-checklist.md' in index_text
    assert 'docs/reference/analysis-domain-capability-matrix.md' in index_text
    assert 'docs/reference/analysis-domain-onboarding-contract.md' in index_text
    assert 'docs/plans/templates/analysis-domain-extension-template.md' in index_text

    onboarding_text = Path('docs/reference/analysis-domain-onboarding-template.md').read_text(encoding='utf-8')
    for keyword in [
        'manifest',
        'artifact',
        'strategy',
        'specialist',
        'report plane',
        'review queue',
        'fixtures',
        'flags',
        'observability',
    ]:
        assert keyword in onboarding_text.lower()
    assert 'analysis-domain-onboarding-contract.md' in onboarding_text
    assert 'docs/plans/templates/analysis-domain-extension-template.md' in onboarding_text

    checklist_text = Path('docs/reference/analysis-domain-checklist.md').read_text(encoding='utf-8')
    assert 'feature flags' in checklist_text.lower()
    assert 'analysis report plane' in checklist_text.lower()
    assert 'review queue' in checklist_text.lower()
    assert 'scripts/analysis_strategy_eval.py' in checklist_text
    assert 'analysis-domain-onboarding-contract.md' in checklist_text
    assert 'docs/plans/templates/analysis-domain-extension-template.md' in checklist_text

    module_boundaries_text = Path('docs/architecture/module-boundaries.md').read_text(encoding='utf-8')
    assert 'analysis-domain-onboarding-template.md' in module_boundaries_text
