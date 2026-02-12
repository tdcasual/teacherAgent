# Backend Quality Hardening Report (Interim)

Date: 2026-02-12
Scope: Week 1 + Week 2 Task 8 + Phase-2 continuation snapshot

## 1) Baseline vs Current

| Metric | Baseline | Current | Delta | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Ruff errors (`ruff check services/api --statistics`) | 745 | 661 | -84 | 11.3% |
| Mypy errors (`mypy --follow-imports=skip services/api`) | 482 | 181 | -301 | 62.4% |
| `services/api/app_core.py` line count | 700 | 595 | -105 | 15.0% |

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
- `python3 -m ruff check services/api/auth_service.py services/api/queue/queue_backend_factory.py services/api/settings.py services/api/runtime/lifecycle.py tests/test_queue_backend_factory.py tests/test_security_auth_hardening.py`
- `python3 -m ruff check services/api/llm_routing.py tests/test_llm_routing_types.py tests/test_app_core_structure.py`
- `python3 -m mypy --follow-imports=skip services/api/auth_service.py services/api/queue/queue_backend_factory.py services/api/settings.py services/api/runtime/lifecycle.py services/api/llm_routing.py`

Metric collection commands:

- `python3 -m ruff check services/api --statistics`
- `python3 -m mypy --follow-imports=skip services/api`
- `wc -l services/api/app_core.py`

## 4) Exit Criteria Status

Criteria from the 2-week plan are partially met:

1. Ruff reduction >=30%: **Not met** (current 11.3%).
2. Mypy reduction >=35%: **Met** (current 62.4%).
3. `app_core.py` <=500 lines: **Not met** (current 595).
4. CI backend-quality guardrails integrated: **Met**.
5. Newly added guardrail tests pass locally: **Met**.

## 5) Remaining Risks

1. `services/api/app_core.py` still carries high coupling and static debt.
2. Global Ruff debt remains high in `services/api` and limits stricter CI adoption.
3. Mypy debt is reduced but still concentrated in older modules not yet isolated.

## 6) Next-Phase Focus

1. Continue extracting cohesive slices from `app_core` (runtime wiring vs route handlers).
2. Target top Ruff hotspots by file-level error density; enforce per-file budgets.
3. Expand mypy scope in CI with module allowlist rotation and hard fail for touched files.
