# Maintainability And Architecture Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** In 2 weeks, improve maintainability and architecture boundaries without breaking behavior by adding quality gates, introducing explicit dependency injection, splitting oversized modules, and reducing frontend bundle risk.

**Architecture:** Keep current FastAPI + React structure, but move from implicit global wiring to explicit container-based composition. Refactor by bounded context slices (`chat`, `exam`, `assignment`) and keep each task small, test-first, and reversible.

**Tech Stack:** Python 3.9+, FastAPI, pytest, React 19, TypeScript, Vite 7, Playwright, GitHub Actions.

---

## Scope And Guardrails

- Do not change endpoint contracts unless tests/documentation are updated in the same task.
- Every task follows TDD: failing test first, minimal implementation, full related tests, then commit.
- Keep each commit focused on one concern and one verification command set.
- Keep deployment safety: no secrets in code, no auth weakening, no destructive migration.

## Baseline Metrics To Capture (Task 0)

Before refactor, record baseline for comparison:
- `python3 -m pytest -q`
- `npm run typecheck` in `/Users/lvxiaoer/Documents/New project/frontend`
- `npm run build:student` and capture largest chunk warning
- `wc -l /Users/lvxiaoer/Documents/New project/services/api/app_core.py`
- `wc -l /Users/lvxiaoer/Documents/New project/frontend/apps/student/src/App.tsx`

Commit message: `chore: capture maintainability baseline metrics`

### Task 1: Add Backend Quality Gates (lint/format/type)

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/pyproject.toml`
- Create: `/Users/lvxiaoer/Documents/New project/.pre-commit-config.yaml`
- Modify: `/Users/lvxiaoer/Documents/New project/.github/workflows/ci.yml`
- Modify: `/Users/lvxiaoer/Documents/New project/README.md`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_app_core_surface.py`

**Step 1: Write the failing test/check**

Add CI job reference in testable workflow expectation by asserting new job names in a lightweight workflow test (create if missing):

```python
def test_ci_contains_quality_jobs():
    text = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'backend-quality' in text
    assert 'frontend-quality' in text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_ci_workflow_quality.py::test_ci_contains_quality_jobs`
Expected: FAIL because `backend-quality` job does not exist yet.

**Step 3: Write minimal implementation**

- Add `ruff`, `black`, `mypy` config to `pyproject.toml`.
- Add pre-commit hooks for `ruff`, `black`, `prettier`.
- Add `backend-quality` job in CI with:
  - `ruff check services tests`
  - `black --check services tests`
  - `mypy services/api`

**Step 4: Run tests/checks to verify pass**

- `python3 -m pytest -q tests/test_ci_workflow_quality.py::test_ci_contains_quality_jobs`
- `python3 -m ruff check services tests`
- `python3 -m black --check services tests`

**Step 5: Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml .github/workflows/ci.yml README.md tests/test_ci_workflow_quality.py
git commit -m "chore(ci): add backend quality gates and pre-commit"
```

### Task 2: Add Frontend ESLint + Prettier Gate

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/frontend/eslint.config.js`
- Create: `/Users/lvxiaoer/Documents/New project/frontend/.prettierrc.json`
- Modify: `/Users/lvxiaoer/Documents/New project/frontend/package.json`
- Modify: `/Users/lvxiaoer/Documents/New project/.github/workflows/ci.yml`
- Test: `/Users/lvxiaoer/Documents/New project/frontend/apps/teacher/src/App.tsx`

**Step 1: Write failing test/check**

Add script expectation test:

```python
def test_frontend_has_lint_script():
    pkg = json.loads(Path('frontend/package.json').read_text())
    assert 'lint' in pkg['scripts']
    assert 'format:check' in pkg['scripts']
```

**Step 2: Run test to verify fail**

Run: `python3 -m pytest -q tests/test_frontend_scripts.py::test_frontend_has_lint_script`
Expected: FAIL because scripts are missing.

**Step 3: Write minimal implementation**

- Add scripts:
  - `lint`: `eslint "apps/**/*.{ts,tsx}"`
  - `format:check`: `prettier --check "apps/**/*.{ts,tsx,css}"`
- Add CI steps in `frontend-quality` job.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_frontend_scripts.py::test_frontend_has_lint_script`
- `npm run lint` (in frontend)
- `npm run format:check` (in frontend)

**Step 5: Commit**

```bash
git add frontend/eslint.config.js frontend/.prettierrc.json frontend/package.json .github/workflows/ci.yml tests/test_frontend_scripts.py
git commit -m "chore(frontend): enforce eslint and prettier in CI"
```

### Task 3: Introduce Explicit App Container

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/container.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/runtime/lifecycle.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_app_container.py`

**Step 1: Write failing test**

```python
def test_app_has_container_on_startup(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert hasattr(client.app.state, 'container')
```

**Step 2: Run test to fail**

Run: `python3 -m pytest -q tests/test_app_container.py::test_app_has_container_on_startup`
Expected: FAIL because container not attached.

**Step 3: Minimal implementation**

- Create `AppContainer` dataclass with fields for settings, queue backend factory, and service factories.
- Build container in app startup and attach to `app.state.container`.
- Read dependencies from container in route registration path.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_app_container.py::test_app_has_container_on_startup`
- `python3 -m pytest -q tests/test_app_core_surface.py`

**Step 5: Commit**

```bash
git add services/api/container.py services/api/app.py services/api/runtime/lifecycle.py tests/test_app_container.py
git commit -m "refactor(api): add explicit app container lifecycle"
```

### Task 4: Remove Implicit Core Proxy Usage In New Code Paths

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_routes.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/wiring.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_app_routes_registration.py`

**Step 1: Write failing test**

```python
def test_register_routes_uses_container_core(fake_app, fake_core):
    register_routes(fake_app, fake_core)
    assert fake_app.include_router.call_count >= 1
```

**Step 2: Run failing test**

Run: `python3 -m pytest -q tests/test_app_routes_registration.py::test_register_routes_uses_container_core`
Expected: FAIL due to old implicit path assumptions.

**Step 3: Minimal implementation**

- Ensure route registration depends on explicit `core` object from container context.
- Keep compatibility shim, but stop adding new dependencies through module-level globals.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_app_routes_registration.py`
- `python3 -m pytest -q tests/test_chat_routes.py tests/test_exam_routes.py`

**Step 5: Commit**

```bash
git add services/api/app.py services/api/app_routes.py services/api/wiring.py tests/test_app_routes_registration.py
git commit -m "refactor(api): route registration via explicit core context"
```

### Task 5: Stabilize Chat Worker Lifecycle (fix thread warnings)

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/workers/chat_worker_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/runtime/queue_runtime.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/chat_lane_repository.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_chat_worker_service.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_runtime_manager.py`

**Step 1: Write failing test**

```python
def test_worker_shutdown_is_graceful_without_unhandled_thread_exception():
    manager = build_runtime_manager_for_test()
    manager.start()
    manager.stop()
    assert manager.last_error is None
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_chat_worker_service.py::test_worker_shutdown_is_graceful_without_unhandled_thread_exception`
Expected: FAIL or flaky failure.

**Step 3: Minimal implementation**

- Add `threading.Event` stop signal.
- Add guarded lane map access when core state is not initialized.
- Ensure runtime `stop` joins worker threads with timeout and logs cleanly.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_chat_worker_service.py tests/test_runtime_manager.py`
- `python3 -m pytest -q` (full)

**Step 5: Commit**

```bash
git add services/api/workers/chat_worker_service.py services/api/runtime/queue_runtime.py services/api/chat_lane_repository.py tests/test_chat_worker_service.py tests/test_runtime_manager.py
git commit -m "fix(worker): deterministic chat worker lifecycle and shutdown"
```

### Task 6: Introduce Chat Job State Machine

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/chat_job_state_machine.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/chat_status_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/chat_job_processing_service.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_chat_status_flow.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_chat_job_flow.py`

**Step 1: Write failing test**

```python
def test_chat_job_rejects_invalid_transition():
    sm = ChatJobStateMachine('done')
    with pytest.raises(ValueError):
        sm.transition('processing')
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_chat_job_flow.py::test_chat_job_rejects_invalid_transition`
Expected: FAIL because no state machine exists.

**Step 3: Minimal implementation**

- Implement allowed transitions map in `chat_job_state_machine.py`.
- Route all transition writes through state machine helper.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_chat_job_flow.py tests/test_chat_status_flow.py`

**Step 5: Commit**

```bash
git add services/api/chat_job_state_machine.py services/api/chat_status_service.py services/api/chat_job_processing_service.py tests/test_chat_job_flow.py tests/test_chat_status_flow.py
git commit -m "refactor(chat): centralize chat job transitions via state machine"
```

### Task 7: Split `exam` Application Slice Out Of app_core

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/exam/application.py`
- Create: `/Users/lvxiaoer/Documents/New project/services/api/exam/deps.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/routes/exam_routes.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_exam_routes.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_exam_endpoints.py`

**Step 1: Write failing test**

```python
def test_exam_routes_call_exam_application_layer(mocker):
    spy = mocker.patch('services.api.exam.application.get_exam_detail')
    client.get('/exam/demo')
    spy.assert_called_once()
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_exam_routes.py::test_exam_routes_call_exam_application_layer`
Expected: FAIL because route still calls old core path.

**Step 3: Minimal implementation**

- Move exam orchestration from app_core to `exam/application.py`.
- Keep pure data assembly in application, no FastAPI imports.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_exam_routes.py tests/test_exam_endpoints.py`

**Step 5: Commit**

```bash
git add services/api/exam/application.py services/api/exam/deps.py services/api/app_core.py services/api/routes/exam_routes.py tests/test_exam_routes.py tests/test_exam_endpoints.py
git commit -m "refactor(exam): extract exam application slice from app_core"
```

### Task 8: Split `assignment` Application Slice Out Of app_core

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/assignment/application.py`
- Create: `/Users/lvxiaoer/Documents/New project/services/api/assignment/deps.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/routes/assignment_routes.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_assignment_routes.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_assignment_handlers.py`

**Step 1: Write failing test**

```python
def test_assignment_routes_call_assignment_application_layer(mocker):
    spy = mocker.patch('services.api.assignment.application.list_assignments')
    client.get('/assignments')
    spy.assert_called_once()
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_assignment_routes.py::test_assignment_routes_call_assignment_application_layer`
Expected: FAIL.

**Step 3: Minimal implementation**

- Move assignment orchestration logic to `assignment/application.py`.
- Keep route handlers thin and declarative.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_assignment_routes.py tests/test_assignment_handlers.py`

**Step 5: Commit**

```bash
git add services/api/assignment/application.py services/api/assignment/deps.py services/api/app_core.py services/api/routes/assignment_routes.py tests/test_assignment_routes.py tests/test_assignment_handlers.py
git commit -m "refactor(assignment): extract assignment application slice from app_core"
```

### Task 9: Split Frontend Student App Shell And Feature Modules

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/frontend/apps/student/src/features/session/StudentSessionShell.tsx`
- Create: `/Users/lvxiaoer/Documents/New project/frontend/apps/student/src/features/chat/StudentChatPanel.tsx`
- Create: `/Users/lvxiaoer/Documents/New project/frontend/apps/student/src/features/workbench/StudentWorkbench.tsx`
- Modify: `/Users/lvxiaoer/Documents/New project/frontend/apps/student/src/App.tsx`
- Test: `/Users/lvxiaoer/Documents/New project/frontend/e2e/student-learning-loop.spec.ts`
- Test: `/Users/lvxiaoer/Documents/New project/frontend/e2e/student-high-risk-resilience.spec.ts`

**Step 1: Write failing test**

Add e2e assertion for shell render contract:

```ts
test('student shell renders chat and workbench regions', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('student-chat-panel')).toBeVisible();
  await expect(page.getByTestId('student-workbench')).toBeVisible();
});
```

**Step 2: Run fail check**

Run: `npm run e2e:student -- e2e/student-learning-loop.spec.ts --grep "student shell renders chat and workbench regions"`
Expected: FAIL (missing stable region markers).

**Step 3: Minimal implementation**

- Extract shell subcomponents from `App.tsx`.
- Add stable `data-testid` contract.

**Step 4: Verify pass**

- `npm run typecheck`
- `npm run e2e:student -- e2e/student-learning-loop.spec.ts`

**Step 5: Commit**

```bash
git add frontend/apps/student/src/App.tsx frontend/apps/student/src/features/session/StudentSessionShell.tsx frontend/apps/student/src/features/chat/StudentChatPanel.tsx frontend/apps/student/src/features/workbench/StudentWorkbench.tsx frontend/e2e/student-learning-loop.spec.ts
git commit -m "refactor(student-ui): split app shell into feature modules"
```

### Task 10: Frontend Bundle Optimization (student chunk warning)

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/frontend/apps/student/src/App.tsx`
- Modify: `/Users/lvxiaoer/Documents/New project/frontend/vite.student.config.ts`
- Modify: `/Users/lvxiaoer/Documents/New project/frontend/apps/shared/markdown.ts`
- Test: `/Users/lvxiaoer/Documents/New project/frontend/e2e/platform-consistency-security.spec.ts`

**Step 1: Write failing threshold test**

Create a lightweight bundle budget script test:

```python
def test_student_main_chunk_under_budget():
    size_kb = read_student_main_chunk_kb('frontend/dist-student/assets')
    assert size_kb < 550
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_frontend_bundle_budget.py::test_student_main_chunk_under_budget`
Expected: FAIL with current ~686kB output.

**Step 3: Minimal implementation**

- Lazy-load markdown/Katex heavy path in student UI.
- Add `manualChunks` strategy in Vite student config.

**Step 4: Verify pass**

- `npm run build:student`
- `python3 -m pytest -q tests/test_frontend_bundle_budget.py::test_student_main_chunk_under_budget`

**Step 5: Commit**

```bash
git add frontend/apps/student/src/App.tsx frontend/vite.student.config.ts frontend/apps/shared/markdown.ts tests/test_frontend_bundle_budget.py
git commit -m "perf(student-ui): split heavy markdown bundle and enforce budget"
```

### Task 11: Architecture Docs And Module Ownership

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/docs/architecture/module-boundaries.md`
- Create: `/Users/lvxiaoer/Documents/New project/docs/architecture/ownership-map.md`
- Modify: `/Users/lvxiaoer/Documents/New project/README.md`
- Modify: `/Users/lvxiaoer/Documents/New project/docs/http_api.md`

**Step 1: Write failing doc test**

```python
def test_architecture_docs_exist():
    assert Path('docs/architecture/module-boundaries.md').exists()
    assert Path('docs/architecture/ownership-map.md').exists()
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_docs_architecture_presence.py::test_architecture_docs_exist`
Expected: FAIL.

**Step 3: Minimal implementation**

- Document layer boundaries and allowed dependencies.
- Add ownership by bounded context and change checklist.

**Step 4: Verify pass**

- `python3 -m pytest -q tests/test_docs_architecture_presence.py::test_architecture_docs_exist`

**Step 5: Commit**

```bash
git add docs/architecture/module-boundaries.md docs/architecture/ownership-map.md README.md docs/http_api.md tests/test_docs_architecture_presence.py
git commit -m "docs(architecture): define module boundaries and ownership"
```

### Task 12: Final Quality Gate And Report

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/docs/plans/2026-02-12-maintainability-architecture-refactor-report.md`
- Modify: `/Users/lvxiaoer/Documents/New project/.github/workflows/ci.yml`

**Step 1: Write failing regression check**

```python
def test_report_contains_target_metrics():
    text = Path('docs/plans/2026-02-12-maintainability-architecture-refactor-report.md').read_text()
    assert 'app_core lines' in text
    assert 'student chunk size' in text
```

**Step 2: Run fail check**

Run: `python3 -m pytest -q tests/test_refactor_report.py::test_report_contains_target_metrics`
Expected: FAIL until report is created.

**Step 3: Minimal implementation**

- Add report with before/after metrics:
  - `app_core.py` line count target: reduce by 35%+
  - `frontend/apps/student/src/App.tsx` line count target: reduce by 40%+
  - student main chunk target: `<550kB`
  - full pytest still green
- Ensure CI runs quality + smoke + build jobs.

**Step 4: Verify pass**

- `python3 -m pytest -q`
- `npm run typecheck`
- `npm run build:teacher && npm run build:student`

**Step 5: Commit**

```bash
git add docs/plans/2026-02-12-maintainability-architecture-refactor-report.md .github/workflows/ci.yml tests/test_refactor_report.py
git commit -m "chore: finalize refactor quality report and enforce gates"
```

## 2-Week Scheduling Guide

- Day 1-2: Task 0-2 (quality baseline and CI gates)
- Day 3-4: Task 3-4 (container and explicit core wiring)
- Day 5-6: Task 5-6 (worker lifecycle + chat state machine)
- Day 7-9: Task 7-8 (exam/assignment extraction)
- Day 10-11: Task 9-10 (student app split + bundle optimization)
- Day 12-13: Task 11 (architecture docs)
- Day 14: Task 12 (final regression run + report)

## Definition Of Done

- `python3 -m pytest -q` passes locally.
- Frontend `typecheck` and both builds pass in CI.
- No new thread warnings in chat worker tests.
- `app_core.py` and student `App.tsx` significantly reduced.
- Docs updated for boundaries and ownership.
- All changes shipped as small, reversible commits.
