from __future__ import annotations

from pathlib import Path


def test_teacher_memory_core_no_longer_defines_context_helpers() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'def _teacher_session_summary_text(' not in source
    assert 'def _teacher_memory_context_text(' not in source



def test_teacher_memory_core_no_longer_defines_mem0_bridge_helpers() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'def _teacher_mem0_search(' not in source
    assert 'def _teacher_mem0_should_index_target(' not in source
    assert 'def _teacher_mem0_index_entry(' not in source



def test_teacher_memory_core_keeps_public_facade_entries_only() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'def teacher_memory_propose(' in source
    assert 'def teacher_memory_apply(' in source
    assert 'def teacher_build_context(' in source
