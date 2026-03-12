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


def test_teacher_memory_core_uses_no_star_imports() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'import *' not in source


def test_teacher_memory_core_declares_explicit_public_exports() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert '__all__ = [' in source
    assert "'teacher_memory_propose'" in source or '"teacher_memory_propose"' in source
    assert "'teacher_memory_apply'" in source or '"teacher_memory_apply"' in source
    assert "'teacher_build_context'" in source or '"teacher_build_context"' in source


def test_teacher_memory_core_no_longer_keeps_internal_rule_store_wrappers() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'def _teacher_memory_parse_dt(' not in source
    assert 'def _teacher_memory_record_ttl_days(' not in source
    assert 'def _teacher_memory_rank_score(' not in source
    assert 'def _teacher_memory_load_record(' not in source
    assert 'def _teacher_memory_recent_proposals(' not in source
    assert 'def _teacher_session_compaction_cycle_no(' not in source
