"""Teacher domain deps builders — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "_teacher_provider_registry_deps",
    "_teacher_llm_routing_deps",
    "_teacher_routing_api_deps",
    "_teacher_assignment_preflight_deps",
]

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..teacher_assignment_preflight_service import TeacherAssignmentPreflightDeps
from ..teacher_llm_routing_service import TeacherLlmRoutingDeps
from ..teacher_provider_registry_service import TeacherProviderRegistryDeps
from ..teacher_routing_api_service import TeacherRoutingApiDeps


from . import get_app_core as _app_core


def _teacher_provider_registry_deps():
    _ac = _app_core()
    return TeacherProviderRegistryDeps(
        model_registry=_ac.LLM_GATEWAY.registry,
        resolve_teacher_id=_ac.resolve_teacher_id,
        teacher_workspace_dir=_ac.teacher_workspace_dir,
        atomic_write_json=_ac._atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        getenv=os.getenv,
    )


def _teacher_llm_routing_deps():
    _ac = _app_core()
    return TeacherLlmRoutingDeps(
        model_registry=_ac.LLM_GATEWAY.registry,
        resolve_model_registry=lambda teacher_id: _ac._merged_model_registry_impl(teacher_id, deps=_ac._teacher_provider_registry_deps()),
        resolve_teacher_id=_ac.resolve_teacher_id,
        teacher_llm_routing_path=_ac.teacher_llm_routing_path,
        legacy_routing_path=_ac.LLM_ROUTING_PATH,
        atomic_write_json=_ac._atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _teacher_routing_api_deps():
    _ac = _app_core()
    return TeacherRoutingApiDeps(teacher_llm_routing_get=_ac.teacher_llm_routing_get)


def _teacher_assignment_preflight_deps():
    _ac = _app_core()
    return TeacherAssignmentPreflightDeps(
        app_root=_ac.APP_ROOT,
        detect_assignment_intent=_ac.detect_assignment_intent,
        llm_assignment_gate=_ac.llm_assignment_gate,
        diag_log=_ac.diag_log,
        allowed_tools=_ac.allowed_tools,
        parse_date_str=_ac.parse_date_str,
        today_iso=_ac.today_iso,
        format_requirements_prompt=_ac.format_requirements_prompt,
        save_assignment_requirements=_ac.save_assignment_requirements,
        assignment_generate=_ac.assignment_generate,
        extract_exam_id=_ac.extract_exam_id,
        exam_get=_ac.exam_get,
    )
