# Platform Simplification Deletions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove task-based model routing, remove persona system, and remove loose teacher skill system across backend/frontend/tests with no compatibility shims.

**Architecture:** Collapse model selection into one teacher-level model-purpose config (`conversation`, `embedding`, `ocr`, `image_generation`) plus provider registry. Keep strict static skills only. Remove all persona-related request/route/runtime branches and remove dynamic teacher skill CRUD/import/runtime.

**Tech Stack:** FastAPI backend, React + TypeScript frontend, pytest + vitest.

---

### Task 1: Remove routing pipeline and introduce simple model config

**Files:**
- Modify: `services/api/chat_runtime_service.py`, `services/api/wiring/chat_wiring.py`, `services/api/wiring/teacher_wiring.py`, `services/api/routes/teacher_routes.py`
- Create: `services/api/teacher_model_config_service.py`, `services/api/routes/teacher_model_config_routes.py`
- Remove/stop wiring: `services/api/routes/teacher_llm_routing_routes.py`, `services/api/teacher_llm_routing_service.py`, `services/api/teacher_routing_api_service.py`

**Steps:**
1. Add failing backend tests for new `/teacher/model-config` GET/PUT and removed `/teacher/llm-routing*` endpoints.
2. Implement `teacher_model_config_service` with teacher-scoped JSON persistence and provider/mode/model validation.
3. Register new model-config routes; unregister llm-routing routes.
4. Refactor `call_llm_runtime` to use teacher `conversation` model config only (fallback to gateway default).
5. Remove routing-specific dependencies/imports from wiring/facade/tool dispatch.

### Task 2: Remove persona backend + request/runtime coupling

**Files:**
- Modify: `services/api/api_models.py`, `services/api/chat_start_service.py`, `services/api/chat_job_processing_service.py`, `services/api/routes/student_routes.py`, `services/api/routes/teacher_routes.py`, `services/api/wiring/chat_wiring.py`, `services/api/wiring/student_wiring.py`, `services/api/wiring/teacher_wiring.py`, `services/api/app_core_service_imports.py`, `services/api/context_runtime_facade.py`
- Remove: `services/api/routes/student_persona_routes.py`, `services/api/routes/teacher_persona_routes.py`, `services/api/student_persona_api_service.py`, `services/api/teacher_persona_api_service.py`

**Steps:**
1. Add failing tests asserting persona routes are absent.
2. Remove persona route registrations from teacher/student routers.
3. Remove `persona_id` request fields from models/start payload/fingerprint and runtime persona branch.
4. Remove persona service imports/deps from core wiring/facades.
5. Delete persona route/service modules.

### Task 3: Remove loose skill system + dynamic tool runtime

**Files:**
- Modify: `services/api/routes/skill_routes.py`, `services/api/wiring/skill_wiring.py`, `services/api/wiring/misc_wiring.py`, `services/api/agent_service.py`, `services/api/skills/runtime.py`, `services/api/skills/loader.py`, `services/api/content_catalog_service.py`, `services/api/chat_support_service.py`, `services/api/tool_dispatch_service.py`, `services/common/tool_registry.py`, `services/api/skills/auto_route_rules.py`
- Remove: `services/api/routes/skill_crud_routes.py`, `services/api/routes/skill_import_routes.py`, `services/api/teacher_skill_service.py`, `services/api/dynamic_skill_tools.py`, `skills/physics-llm-routing`

**Steps:**
1. Add failing tests for absence of `/teacher/skills*` endpoints and absence of `teacher.llm_routing.*` tools.
2. Remove CRUD/import routes and wiring surface.
3. Remove dynamic tools from skill runtime + agent tool conversion path.
4. Simplify skill loader to strict static sources only (no teacher custom folder overlay).
5. Remove obsolete routing skill rule and fallback skill entry.

### Task 4: Simplify teacher/student frontend

**Files:**
- Modify: `frontend/apps/teacher/src/App.tsx`, `frontend/apps/teacher/src/features/settings/TeacherSettingsPanel.tsx`, `frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx`, `frontend/apps/teacher/src/features/chat/useTeacherUiPanels.ts`, `frontend/apps/teacher/src/features/state/useLocalStorageSync.ts`, `frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx`, `frontend/apps/teacher/src/features/workbench/tabs/SkillsTab.tsx`, `frontend/apps/teacher/src/features/chat/catalog.ts`, `frontend/apps/teacher/src/appTypes.ts`
- Create: `frontend/apps/teacher/src/features/settings/ModelSettingsPage.tsx`
- Remove: `frontend/apps/teacher/src/features/routing/*`, `frontend/apps/teacher/src/features/persona/*`
- Modify: `frontend/apps/student/src/App.tsx`, `frontend/apps/student/src/features/layout/StudentTopbar.tsx`, `frontend/apps/student/src/hooks/useStudentState.ts`, `frontend/apps/student/src/features/chat/useStudentSendFlow.ts`, `frontend/apps/student/src/appTypes.ts`

**Steps:**
1. Replace routing UI with model settings UI (providers + purpose models).
2. Remove teacher persona manager entry and component usage.
3. Make skills tab readonly/list+select only (no create/import/edit/delete).
4. Remove student persona controls/state/send parameter and related types.
5. Remove now-dead imports/storage keys and routing section types.

### Task 5: Tests + docs cleanup + verification

**Files:**
- Modify/remove affected tests under `tests/` and frontend test files
- Update docs: `README.md`, `docs/http_api.md` (if routes documented)

**Steps:**
1. Delete tests that exclusively target removed features (routing endpoints/persona CRUD/teacher skill CRUD-import/dynamic tools).
2. Update route-structure and frontend-structure tests to new invariants.
3. Add coverage for model-config endpoint behavior and runtime model selection fallback path.
4. Run backend + frontend test/typecheck/lint/build commands.
5. Report exact pass/fail evidence and remaining gaps.
