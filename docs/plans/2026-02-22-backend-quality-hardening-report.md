# Backend Quality Hardening Report (Interim)
提炼去向：`docs/explain/backend-quality-hardening-overview.md`

Date: 2026-02-12
Scope: Week 1 + Week 2 Task 8 + Phase-2 continuation snapshot

## 1) Baseline vs Current

| Metric | Baseline | Current | Delta | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Ruff errors (`ruff check services/api --statistics`) | 745 | 332 | -413 | 55.4% |
| Mypy errors (`mypy --follow-imports=skip services/api`) | 482 | 0 | -482 | 100.0% |
| `services/api/app_core.py` line count | 700 | 261 | -439 | 62.7% |

## 2) Completed Changes

1. Added quality baseline + budget artifacts and collector script.
2. Added guardrail tests for star imports and duplicate route files.
3. Removed star imports from `services/api/llm_routing.py` with explicit exports.
4. Hardened malformed nested config handling in `services/api/teacher_provider_registry_service.py`.
5. Extracted chat limiter/concurrency helpers from `services/api/app_core.py` to `services/api/chat_limits.py`.
6. Expanded CI static scope (`.github/workflows/ci.yml`) and added `tests/test_ci_backend_scope.py`.
7. Hardened production runtime policy:
   - `AUTH_REQUIRED=1` + missing `AUTH_TOKEN_SECRET` now fails fast in production lifecycle startup.
   - Queue backend no longer silently falls back to inline in production unless explicitly allowed.
8. Removed duplicate explicit re-export import blocks in `services/api/app_core.py`, reducing facade bloat.
9. Cleared `services/api/llm_routing.py` mypy `union-attr` debt with dict/list type narrowing helpers and added a focused type gate.
10. Cleared `services/api/llm_routing_resolver.py` mypy `union-attr` debt and expanded type gate coverage.
11. Cleared `services/api/exam_upload_parse_service.py` mypy `union-attr`/`arg-type` hotspots and added a focused type gate.
12. Added full type annotations to `services/api/runtime/queue_runtime.py` and added a focused type gate.
13. Cleared `services/api/exam_upload_confirm_service.py` mypy schema/merge typing hotspots and added a focused type gate.
14. Cleared `services/api/exam_analysis_charts_service.py` mypy call-arg hotspots and added a focused type gate.
15. Added return annotations for `services/api/assignment/application.py` async entrypoints and added a focused type gate.
16. Cleared `services/api/chart_agent_run_service.py` mypy call-signature/arg-type hotspots and added a focused type gate.
17. Added return annotations for `services/api/exam/application.py` sync/async entrypoints and added a focused type gate.
18. Cleared `services/api/skills/spec.py` mypy union-attr hotspots and added a focused type gate.
19. Cleared `services/api/exam_range_service.py` `safe_int_arg` call-signature hotspots and added a focused type gate.
20. Cleared `services/api/exam_overview_service.py` fallback normalization/sort typing hotspots and added a focused type gate.
21. Cleared `services/api/exam_upload_api_service.py` schema normalization/merge typing hotspots and added a focused type gate.
22. Added explicit annotations to `services/api/handlers/exam_upload_handlers.py` async entrypoints and added a focused type gate.
23. Relaxed callable signatures in `services/api/tool_dispatch_service.py` to accept keyword-based adapter calls and added a focused type gate.
24. Widened resolver callable signatures in `services/api/lesson_core_tool_service.py` and `services/api/core_example_tool_service.py` for keyword-safe adapter calls, and added focused type gates.
25. Tightened request dict narrowing and callable signatures in `services/api/chat_lane_service.py`, and added a focused type gate.
26. Narrowed student id list extraction in `services/api/student_directory_service.py` and added a focused type gate.
27. Removed optional-to-str reassignment hotspot in `services/api/exam_longform_service.py` and added a focused type gate.
28. Normalized correctness parsing and positional `safe_int_arg` call in `services/api/exam_detail_service.py`, and added a focused type gate.
29. Added return annotations for `services/api/routes/student_profile_routes.py` handlers and added a focused type gate.
30. Added return annotations for `services/api/routes/student_history_routes.py` handlers and added a focused type gate.
31. Added return annotations for `services/api/routes/misc_general_routes.py` and `services/api/routes/misc_chart_routes.py`, and added focused type gates.
32. Added return annotations for `services/api/routes/assignment_generation_routes.py` and `services/api/routes/assignment_delivery_routes.py`, and added focused type gates.
33. Tightened numeric/query-stat typing in `services/api/teacher_memory_insights_service.py` and added a focused type gate.
34. Extracted service import fan-out from `services/api/app_core.py` into `services/api/app_core_service_imports.py`, reducing facade size and preserving runtime behavior.
35. Added return annotations across route batches (`student_ops`, `skill_*`, `exam_*`, `assignment_*`, `chat`, `teacher_*`) and introduced a consolidated route type gate.
36. Added async handler/runtime typing pass across `assignment_*_handlers`, `chat_handlers`, `runtime/bootstrap.py`, `workers/inline_runtime.py`, `tenant_admin_api.py`, `chat_job_service.py`, and `app.py`, with a consolidated type gate.
37. Cleared residual mypy hotspots in single-error files (`student_import_service.py`, `teacher_memory_rules_service.py`, `skills/loader.py`, `skills/runtime.py`, `teacher_memory_search_service.py`, `mem0_adapter.py`, `llm_routing_proposals.py`, `exam_upload_draft_service.py`, `core_utils.py`, `teacher_skill_service.py`, `teacher_session_compaction_helpers.py`, `runtime/runtime_state.py`, `tenant_dispatcher.py`, `workers/rq_tenant_runtime.py`).
38. Cleared wiring/deps signature mismatches in `wiring/chat_wiring.py`, `wiring/skill_wiring.py`, `wiring/worker_wiring.py`, `wiring/exam_wiring.py`, `wiring/assignment_wiring.py`, `wiring/misc_wiring.py`, `exam/deps.py`, and `assignment/deps.py`.
39. Cleared remaining union/call-arg hotspots in `chat_job_processing_service.py`, `exam_score_processing_service.py`, `subject_score_guard_service.py`, `session_view_state.py`, `chat_history_store.py`, and `chat_lane_repository.py`, bringing full backend mypy to zero.

## 3) Validation Evidence

Executed and passed (representative list):

- `python3 -m pytest -q tests/test_chat_limits.py tests/test_chat_route_flow.py tests/test_chat_start_flow.py tests/test_app_core_surface.py`
- `python3 -m pytest -q tests/test_ci_backend_scope.py tests/test_ci_workflow_quality.py`
- `python3 -m pytest -q tests/test_security_auth_hardening.py tests/test_queue_backend_factory.py tests/test_tenant_admin_and_dispatcher.py`
- `python3 -m pytest -q tests/test_app_core_structure.py tests/test_app_core_import_fanout.py tests/test_app_core_surface.py`
- `python3 -m pytest -q tests/test_llm_routing_types.py tests/test_llm_routing.py tests/test_llm_routing_resolver.py tests/test_teacher_llm_routing_service.py`
- `python3 -m pytest -q tests/test_exam_range_types.py tests/test_exam_range_service.py`
- `python3 -m pytest -q tests/test_exam_overview_service.py tests/test_exam_overview_types.py`
- `python3 -m pytest -q tests/test_exam_upload_api_service.py tests/test_exam_upload_api_types.py`
- `python3 -m pytest -q tests/test_upload_handlers.py tests/test_exam_upload_handlers_types.py`
- `python3 -m pytest -q tests/test_tool_dispatch_service.py tests/test_tool_dispatch_types.py`
- `python3 -m pytest -q tests/test_lesson_core_tool_service.py tests/test_core_example_tool_service.py tests/test_lesson_core_tool_types.py tests/test_core_example_tool_types.py`
- `python3 -m pytest -q tests/test_chat_lane_service.py tests/test_chat_lane_service_types.py`
- `python3 -m pytest -q tests/test_student_directory_service.py tests/test_student_directory_types.py`
- `python3 -m pytest -q tests/test_exam_longform_service.py tests/test_exam_longform_types.py`
- `python3 -m pytest -q tests/test_exam_detail_service.py tests/test_exam_detail_types.py`
- `python3 -m pytest -q tests/test_student_routes.py tests/test_student_profile_routes_types.py tests/test_student_history_routes_types.py`
- `python3 -m pytest -q tests/test_misc_general_routes_types.py tests/test_misc_chart_routes_types.py tests/test_assignment_generation_routes_types.py tests/test_assignment_delivery_routes_types.py tests/test_teacher_memory_insights_service_types.py tests/test_teacher_memory_insights_service.py`
- `python3 -m pytest -q tests/test_app_core_structure.py tests/test_app_core_decomposition.py tests/test_app_core_import_fanout.py tests/test_app_core_surface.py tests/test_app_routes_registration.py`
- `python3 -m pytest -q tests/test_route_annotation_batch_types.py tests/test_handler_runtime_typing_batch.py tests/test_assignment_handlers.py tests/test_assignment_io_handlers.py tests/test_upload_handlers.py tests/test_chat_handlers.py tests/test_session_discussion_service.py tests/test_session_view_state.py tests/test_chat_history_store.py tests/test_chat_lane_queue.py tests/test_teacher_memory_rules_service.py tests/test_teacher_memory_search_service.py tests/test_teacher_skill_service.py tests/test_exam_score_processing.py tests/test_exam_upload_draft_service.py tests/test_assignment_application_types.py tests/test_exam_application_types.py tests/test_chat_job_processing_service.py tests/test_chat_routes.py tests/test_assignment_routes.py tests/test_teacher_routes.py`
- `python3 -m ruff check services/api/auth_service.py services/api/queue/queue_backend_factory.py services/api/settings.py services/api/runtime/lifecycle.py tests/test_queue_backend_factory.py tests/test_security_auth_hardening.py`
- `python3 -m ruff check services/api/llm_routing.py tests/test_llm_routing_types.py tests/test_app_core_structure.py`
- `python3 -m mypy --follow-imports=skip services/api/auth_service.py services/api/queue/queue_backend_factory.py services/api/settings.py services/api/runtime/lifecycle.py services/api/llm_routing.py`
- `python3 -m mypy --follow-imports=skip services/api`

Metric collection commands:

- `python3 -m ruff check services/api --statistics`
- `python3 -m mypy --follow-imports=skip services/api`
- `wc -l services/api/app_core.py`

## 4) Exit Criteria Status

Criteria from the 2-week plan are partially met:

1. Ruff reduction >=30%: **Met** (current 55.4%).
2. Mypy reduction >=35%: **Met** (current 100.0%).
3. `app_core.py` <=500 lines: **Met** (current 261).
4. CI backend-quality guardrails integrated: **Met**.
5. Newly added guardrail tests pass locally: **Met**.

## 5) Remaining Risks

1. `services/api/app_core.py` is smaller but still carries compatibility-facade star-import coupling.
2. Global Ruff debt remains concentrated in `app_core` compatibility exports and import-order constraints.
3. Mypy baseline is cleared; principal risk is regression if touched-file typing discipline is not maintained.

## 6) Next-Phase Focus

1. Continue extracting `app_core` compatibility exports into typed facades to retire star-import based lookups.
2. Target remaining Ruff hotspots (`F401`/`E402`/`F405`) in `app_core` and wiring modules with compatibility-preserving refactors.
3. Keep touched-file mypy gates strict and fail-fast to preserve the zero-error baseline.
