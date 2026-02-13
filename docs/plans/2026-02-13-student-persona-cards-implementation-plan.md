# Student Persona Cards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Land Phase 1 backend and student integration for persona cards: student persona CRUD/activation, chat payload propagation, and dedup correctness.

**Architecture:** Add a new student persona service (file-backed) and route module under student routes. Extend chat request models with `persona_id`, persist it in chat jobs, and include it in dedup fingerprint seed. Keep persona logic as additive metadata, no behavior break in existing chat path.

**Tech Stack:** FastAPI, Pydantic, Python unittest/pytest, TypeScript React (student sender payload only).

---

### Task 1: Add failing tests for persona APIs and dedup fingerprint

**Files:**
- Create: `tests/test_student_persona_api_service.py`
- Modify: `tests/test_student_routes.py`
- Modify: `tests/test_chat_start_service.py`

**Step 1: Write failing tests**
1. Add tests for listing personas (teacher-assigned + custom approved + active id).
2. Add tests for custom persona cap (`<=5 approved`), create returns validation error when exceeded.
3. Add tests for activate/deactivate and delete custom persona.
4. Add route assertions for new student persona endpoints.
5. Add chat-start test proving dedup fingerprint seed includes `persona_id`.

**Step 2: Run tests to verify failure**
Run: `python3 -m pytest -q tests/test_student_persona_api_service.py tests/test_student_routes.py tests/test_chat_start_service.py`  
Expected: failures due missing service/routes/fields.

### Task 2: Implement backend service and routes

**Files:**
- Create: `services/api/student_persona_api_service.py`
- Create: `services/api/routes/student_persona_routes.py`
- Modify: `services/api/routes/student_routes.py`
- Modify: `services/api/wiring/student_wiring.py`
- Modify: `services/api/app_core_service_imports.py`

**Step 1: Minimal service implementation**
1. Add deps dataclass and APIs:
   - `student_personas_get`
   - `student_persona_custom_create`
   - `student_persona_activate`
   - `student_persona_custom_delete`
2. Implement safe file helpers for:
   - `data/persona_assignments/by_student/<student_id>.json`
   - `data/teacher_personas/<teacher_id>/personas.json`
   - `data/student_profiles/<student_id>.json`
3. Enforce approved custom persona cap at 5.

**Step 2: Route integration**
1. Register `/student/personas` endpoints under student router.
2. Keep route handlers thin and delegate to service APIs.

**Step 3: Run tests**
Run: `python3 -m pytest -q tests/test_student_persona_api_service.py tests/test_student_routes.py`  
Expected: PASS.

### Task 3: Propagate persona_id through chat start + dedup fix

**Files:**
- Modify: `services/api/api_models.py`
- Modify: `services/api/chat_start_service.py`
- Modify: `frontend/apps/student/src/features/chat/useStudentSendFlow.ts`

**Step 1: Extend contracts**
1. Add optional `persona_id` to `ChatRequest` and `ChatStartRequest`.
2. Include `persona_id` in start request payload record.

**Step 2: Dedup seed update**
1. Add `persona_id` into `fingerprint_seed` in chat start service.

**Step 3: Frontend send payload**
1. Add optional `activePersonaId` param into send hook.
2. Include `persona_id` in `/chat/start` request body when present.

**Step 4: Run tests**
Run: `python3 -m pytest -q tests/test_chat_start_service.py tests/test_chat_routes.py`  
Expected: PASS.

### Task 4: Validation sweep and commit

**Files:**
- Verify touched files only.

**Step 1: Run focused validation**
Run:
1. `python3 -m pytest -q tests/test_student_persona_api_service.py tests/test_student_routes.py tests/test_chat_start_service.py tests/test_chat_routes.py`
2. `python3 -m pytest -q tests/test_student_profile_routes_types.py` (mypy gate continuity)

Expected: PASS.

**Step 2: Commit**
```bash
git add services/api/student_persona_api_service.py services/api/routes/student_persona_routes.py services/api/routes/student_routes.py services/api/wiring/student_wiring.py services/api/app_core_service_imports.py services/api/api_models.py services/api/chat_start_service.py frontend/apps/student/src/features/chat/useStudentSendFlow.ts tests/test_student_persona_api_service.py tests/test_student_routes.py tests/test_chat_start_service.py docs/plans/2026-02-13-student-persona-cards-implementation-plan.md
git commit -m "feat(student): add persona APIs and chat persona propagation"
```
