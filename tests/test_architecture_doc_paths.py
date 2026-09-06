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



def test_index_does_not_require_analysis_domain_onboarding_as_product_identity() -> None:
    index_text = Path('docs/INDEX.md').read_text(encoding='utf-8')
    assert 'docs/plans/2026-08-28-assignment-core-product-design.md' in index_text
    # Historical analysis-domain docs may remain on disk; INDEX is not required to list them.
    product_section = index_text.split('## 参考文档', 1)[0]
    assert 'analysis-domain-onboarding' not in product_section
    assert 'analysis-domain-checklist' not in product_section
    assert 'analysis-domain-capability-matrix' not in product_section
    assert 'analysis-domain-onboarding-contract' not in product_section
    assert 'analysis-domain-extension-template' not in product_section
