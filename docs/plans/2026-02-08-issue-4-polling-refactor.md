# Issue 4 Polling Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace manual `setTimeout` polling in Teacher workbench upload status hooks with the shared visibility-aware backoff poller while preserving behavior.

**Architecture:** Add a small guardrail test that enforces shared poller usage and removes manual timers. Refactor the two hooks to call `startVisibilityAwareBackoffPolling`, keep fingerprint-based reset logic, preserve backoff/jitter/hidden delay semantics, and ensure cleanup/abort handling matches prior behavior.

**Tech Stack:** React hooks, TypeScript, Playwright (existing), Python unittest/pytest for guardrail test.

---

### Task 1: Add failing guardrail test (TDD RED)

**Files:**
- Create: `tests/test_issue4_polling_refactor.py`
- Modify: `frontend/apps/shared/visibilityBackoffPolling.ts` (later, for hidden delay option)

**Step 1: Write the failing test**

```python
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useAssignmentUploadStatusPolling.ts"
EXAM = ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "workbench" / "useExamUploadStatusPolling.ts"
POLLER = ROOT / "frontend" / "apps" / "shared" / "visibilityBackoffPolling.ts"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hooks_use_shared_poller_and_no_manual_timers():
    assignment = _read(ASSIGNMENT)
    exam = _read(EXAM)

    assert "startVisibilityAwareBackoffPolling" in assignment
    assert "startVisibilityAwareBackoffPolling" in exam

    for text in (assignment, exam):
        assert "setTimeout" not in text
        assert "visibilitychange" not in text
        assert "document.visibilityState" not in text


def test_exam_hook_preserves_hidden_min_delay():
    exam = _read(EXAM)
    assert "hiddenMinDelayMs" in exam


def test_shared_poller_supports_hidden_min_delay():
    poller = _read(POLLER)
    assert "hiddenMinDelayMs" in poller
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_issue4_polling_refactor.py -v`  
Expected: FAIL (hooks still contain manual timers; poller lacks `hiddenMinDelayMs`).

---

### Task 2: Refactor shared poller for hidden delay support (GREEN)

**Files:**
- Modify: `frontend/apps/shared/visibilityBackoffPolling.ts`

**Step 1: Implement minimal change**

```ts
export type VisibilityBackoffPollingOptions = {
  // ...
  hiddenMinDelayMs?: number
}

// scheduleHidden:
const scheduleHidden = () => {
  const hiddenMin = typeof hiddenMinDelayMs === 'number' ? hiddenMinDelayMs : 0
  schedule(jitter(Math.min(maxDelayMs, Math.max(delayMs, hiddenMin))))
}
```

**Step 2: Run test to verify it still fails for hooks**

Run: `python3 -m pytest tests/test_issue4_polling_refactor.py -v`  
Expected: FAIL (hooks not updated yet).

---

### Task 3: Refactor assignment polling hook (GREEN)

**Files:**
- Modify: `frontend/apps/teacher/src/features/workbench/useAssignmentUploadStatusPolling.ts`

**Step 1: Replace manual timers with shared poller**

Key changes:
- Import `startVisibilityAwareBackoffPolling`.
- Remove `setTimeout`, `visibilitychange`, `delayMs` timers.
- Keep fingerprint logic and `clearActiveUpload`.
- Return `'stop'` for `done/failed/confirmed/created`.
- Use `resetDelay` when fingerprint changes.
- Use `onError` to set error message.

**Step 2: Run test to verify it still fails for exam hook**

Run: `python3 -m pytest tests/test_issue4_polling_refactor.py -v`  
Expected: FAIL (exam hook still has manual timers).

---

### Task 4: Refactor exam polling hook (GREEN)

**Files:**
- Modify: `frontend/apps/teacher/src/features/workbench/useExamUploadStatusPolling.ts`

**Step 1: Replace manual timers with shared poller**

Key changes:
- Import `startVisibilityAwareBackoffPolling`.
- Use `hiddenMinDelayMs: 12000`, `initialDelayMs: 4000`, `maxDelayMs: 30000`, `normalBackoffFactor: 1.25`, `errorBackoffFactor: 1.6`, `jitterMin: 0.8`, `jitterMax: 1.2`.
- Maintain `delayMsRef` in hook to compute `nextDelayMs` when status is terminal and enforce min 9000.
- Update `delayMsRef` on success path and in `onError` to keep in sync with poller.
- Preserve `setExamUploadError` and `clearActiveUpload` logic.

**Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_issue4_polling_refactor.py -v`  
Expected: PASS.

---

### Task 5: Verification + documentation + commit

**Step 1: Typecheck**

Run: `cd frontend && npm run typecheck`  
Expected: PASS.

**Step 2: E2E hard verification**

Run:
- `cd frontend && npm run e2e:teacher`
- `cd frontend && npm run e2e:student`

Expected: PASS.

**Step 3: Update issues doc**

Update: `docs/issues/err-ui-interaction-verified.md`  
Add evidence for Issue 4 (hooks now use shared poller, guardrail test path, and verification commands).

**Step 4: Commit**

```bash
git add tests/test_issue4_polling_refactor.py \
  frontend/apps/shared/visibilityBackoffPolling.ts \
  frontend/apps/teacher/src/features/workbench/useAssignmentUploadStatusPolling.ts \
  frontend/apps/teacher/src/features/workbench/useExamUploadStatusPolling.ts \
  docs/issues/err-ui-interaction-verified.md
git commit -m "refactor: unify workbench polling with shared backoff"
```
