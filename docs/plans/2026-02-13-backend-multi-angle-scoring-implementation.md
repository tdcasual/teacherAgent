# Backend Multi-Angle Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a runnable backend multi-angle scoring tool that computes module/global scores using the validated trend-based formula.

**Architecture:** Add a pure-Python scorer under `scripts/quality` driven by a JSON config + JSON input payload. The scorer computes KPI normalization, state score, trend score, module score, and global risk-weighted score, then emits a JSON report for governance/ops consumption.

**Tech Stack:** Python 3.9, pytest, JSON files, existing `scripts/quality` pattern.

---

### Task 1: Define scoring config and input contract

**Files:**
- Create: `config/backend_multi_angle_scoring.json`
- Modify: `docs/plans/2026-02-13-backend-multi-angle-scoring-design.md`
- Test: `tests/test_backend_multi_angle_scoring.py`

**Step 1: Write the failing test**

Add test asserting config exists and has required module/dimension weights.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py::test_scoring_config_has_required_modules_and_weights`
Expected: FAIL because file or loader does not exist.

**Step 3: Write minimal implementation**

Create config file with module dimension weights + global weighting constants.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py::test_scoring_config_has_required_modules_and_weights`
Expected: PASS.

### Task 2: Implement core scoring functions via TDD

**Files:**
- Create: `scripts/quality/backend_multi_angle_scoring.py`
- Test: `tests/test_backend_multi_angle_scoring.py`

**Step 1: Write the failing test**

Add tests for:
- higher/lower-better KPI normalization
- trend score formula + clamp
- module score formula (`0.7 * state + 0.3 * trend + bonus - penalty`)
- missing KPI dimensions do not force direct zeroing (weight renormalization + insufficient data flag)

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py -k "normalize or trend or module or insufficient"`
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement pure functions:
- `normalize_kpi`
- `compute_trend_score`
- `compute_state_score`
- `compute_module_score`
- `compute_global_score`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py -k "normalize or trend or module or insufficient"`
Expected: PASS.

### Task 3: Implement report builder and CLI

**Files:**
- Modify: `scripts/quality/backend_multi_angle_scoring.py`
- Create: `data/staging/backend_multi_angle_scoring_sample.json`
- Test: `tests/test_backend_multi_angle_scoring.py`

**Step 1: Write the failing test**

Add integration test for full `build_report` output shape and global score from sample payload.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py::test_build_report_outputs_global_and_module_scores`
Expected: FAIL.

**Step 3: Write minimal implementation**

Add CLI args (`--input`, `--config`, `--output`) and JSON report emission.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py::test_build_report_outputs_global_and_module_scores`
Expected: PASS.

### Task 4: Verify and document usage

**Files:**
- Modify: `docs/plans/2026-02-13-backend-multi-angle-scoring-design.md`
- Modify: `docs/http_api.md` (optional pointer if needed)
- Test: `tests/test_backend_multi_angle_scoring.py`

**Step 1: Write the failing test**

Add test for CLI smoke run writing output file.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py::test_cli_writes_report_json`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ensure `main()` returns non-zero on invalid input and writes report on success.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py::test_cli_writes_report_json`
Expected: PASS.

### Task 5: Final verification and commit

**Files:**
- Modify: `tests/test_backend_multi_angle_scoring.py`
- Modify: `scripts/quality/backend_multi_angle_scoring.py`
- Modify: `config/backend_multi_angle_scoring.json`

**Step 1: Run focused test suite**

Run: `python3 -m pytest -q tests/test_backend_multi_angle_scoring.py`
Expected: PASS.

**Step 2: Run format/lint/type checks on changed files**

Run:
- `python3 -m ruff check scripts/quality/backend_multi_angle_scoring.py tests/test_backend_multi_angle_scoring.py`
- `python3 -m mypy --follow-imports=skip scripts/quality/backend_multi_angle_scoring.py`

Expected: PASS.

**Step 3: Commit**

```bash
git add config/backend_multi_angle_scoring.json scripts/quality/backend_multi_angle_scoring.py data/staging/backend_multi_angle_scoring_sample.json tests/test_backend_multi_angle_scoring.py docs/plans/2026-02-13-backend-multi-angle-scoring-design.md docs/plans/2026-02-13-backend-multi-angle-scoring-implementation.md
git commit -m "feat: implement backend multi-angle scoring pipeline"
```
