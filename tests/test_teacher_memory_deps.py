from __future__ import annotations

from pathlib import Path

import services.api.teacher_memory_deps as deps_mod
from services.api.teacher_memory_deps import (
    _teacher_context_deps,
    _teacher_memory_apply_deps,
    _teacher_memory_search_deps,
)


def test_teacher_context_deps_use_teacher_context_service_helpers() -> None:
    deps = _teacher_context_deps()
    assert deps.teacher_session_summary_text.__module__ == 'services.api.teacher_context_service'
    assert deps.teacher_memory_context_text.__module__ == 'services.api.teacher_context_service'



def test_teacher_memory_search_deps_use_mem0_adapter_directly() -> None:
    deps_mod._app_core = lambda: type('AppCore', (), {'diag_log': staticmethod(lambda *a, **k: None)})()
    deps = _teacher_memory_search_deps()
    assert deps.mem0_search.__module__ == 'services.api.mem0_adapter'


def test_teacher_memory_apply_deps_use_mem0_adapter_directly() -> None:
    deps_mod._app_core = lambda: type('AppCore', (), {'diag_log': staticmethod(lambda *a, **k: None)})()
    deps = _teacher_memory_apply_deps()
    assert deps.mem0_should_index_target.__module__ == 'services.api.mem0_adapter'
    assert deps.mem0_index_entry.__module__ == 'services.api.mem0_adapter'



def test_teacher_memory_deps_stop_using_core_private_governance_helpers() -> None:
    source = Path('services/api/teacher_memory_deps.py').read_text(encoding='utf-8')
    assert 'tmc._teacher_memory_find_duplicate' not in source
    assert 'tmc._teacher_memory_auto_quota_reached' not in source
    assert 'tmc._teacher_memory_find_conflicting_applied' not in source
    assert 'tmc._teacher_memory_mark_superseded' not in source
