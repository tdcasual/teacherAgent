# Debt Cleanup Continuation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce remaining backend debt by clearing autofixable lint issues, then shrinking the highest-value `mypy` cluster without destabilizing tests.

**Architecture:** Start with mechanical, low-risk source rewrites that preserve behavior (`ruff --fix`). Then focus on the `teacher_memory_*` typing cluster, because it contains callable signature drift introduced by the recent facade refactor and affects multiple services. Verify each slice with targeted checks before widening back to full-suite validation.

**Tech Stack:** Python, Ruff, mypy, pytest, React/TypeScript (existing frontend regression guard only)

---

### Task 1: Clear autofixable Ruff debt

**Files:**
- Modify: `services/api/**/*.py`
- Modify: `tests/**/*.py`

**Step 1: Reproduce the current lint failures**

Run: `./.venv/bin/python -m ruff check services tests`

Expected: `I001` / `F401` failures only, all fixable.

**Step 2: Apply mechanical fixes**

Run: `./.venv/bin/python -m ruff check --fix services tests`

**Step 3: Verify lint is clean**

Run: `./.venv/bin/python -m ruff check services tests`

Expected: exit `0`.

### Task 2: Fix teacher memory typing drift

**Files:**
- Modify: `services/api/teacher_memory_apply_service.py`
- Modify: `services/api/teacher_memory_search_service.py`
- Modify: `services/api/teacher_context_service.py`
- Modify: `services/api/teacher_memory_deps.py`
- Test: `tests/test_teacher_memory_deps.py`
- Test: `tests/test_teacher_mem0_integration.py`
- Test: `tests/test_teacher_memory_core.py`

**Step 1: Reproduce the focused type failures**

Run: `./.venv/bin/python -m mypy services/api/teacher_memory_deps.py services/api/teacher_memory_apply_service.py services/api/teacher_context_service.py services/api/teacher_memory_search_service.py --follow-imports=skip`

Expected: callable signature mismatches and missing annotations.

**Step 2: Use the existing failing type check as red**

Do not change runtime behavior first; align dependency protocol types and bridge wrappers until the focused mypy command goes green.

**Step 3: Verify focused runtime regressions**

Run: `./.venv/bin/python -m pytest -q tests/test_teacher_memory_deps.py tests/test_teacher_mem0_integration.py tests/test_teacher_memory_core.py`

Expected: pass.

### Task 3: Reassess remaining mypy debt

**Files:**
- Inspect: `services/api/analysis_metrics_service.py`
- Inspect: `services/api/chat_execution_timeline_service.py`
- Inspect: `services/api/chat_job_processing_service.py`
- Inspect: `services/api/analysis_gate_ownership_service.py`
- Inspect: `services/api/review_feedback_service.py`

**Step 1: Re-run backend mypy**

Run: `./.venv/bin/python -m mypy services/api --follow-imports=skip`

Expected: fewer errors than baseline.

**Step 2: Decide whether another slice is still high leverage**

If the remaining errors cluster tightly, fix one more cluster. If they are sparse and low leverage, stop and report the new baseline.

### Task 4: Final verification

**Files:**
- Verify only

**Step 1: Full test suite**

Run: `./.venv/bin/python -m pytest -q`

**Step 2: Quality budget**

Run: `./.venv/bin/python scripts/quality/check_backend_quality_budget.py --print-only`

**Step 3: Report next best slice**

Summarize what remains and whether continuing immediately is still worth it.
