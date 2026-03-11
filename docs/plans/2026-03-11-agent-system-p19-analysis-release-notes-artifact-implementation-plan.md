# Agent System P19 Analysis Release Notes Artifact Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于现有 analysis decision / brief / go-live summary artifacts 生成一个固定模板的 release notes markdown artifact，作为发布记录与发布说明草稿。

**Architecture:** 复用 `analysis-rollout-decision.json`、`analysis-rollout-brief.md`、`analysis-go-live-summary.md`，新增一个轻量 markdown builder 输出 `analysis-release-notes.md`。CI 生成该 artifact 并与其他 analysis artifacts 一起上传；本地也可直接运行同一脚本生成 release notes 草稿。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、Markdown/JSON artifacts、GitHub Actions。

---

### Task 1: Add failing tests for release notes artifact

**Files:**
- Create: `tests/test_analysis_release_notes_builder.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

覆盖以下行为：
- release notes builder 能读取 decision/brief/go-live summary artifacts，输出包含 date、release、summary、decision、verification snapshot、recommended next actions 的 markdown；
- CI workflow 会生成 `analysis-release-notes.md`。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_notes_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement release notes builder and wire CI

**Files:**
- Create: `scripts/quality/build_analysis_release_notes.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write minimal implementation**

- 读取 `analysis-rollout-decision.json`、`analysis-rollout-brief.md`、`analysis-go-live-summary.md`；
- 输出 `analysis-release-notes.md`，至少包含：`Date`、`Release`、`Summary`、`Release Decision`、`Verification Snapshot`、`Recommended Next Actions`；
- 支持 `--date` 与 `--release-ref` 参数，便于 CI 和本地复现；
- CI 在 upload artifact 前生成 release notes 文件。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_notes_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify broadly

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Update docs**

补充：
- `analysis-release-notes.md` 可作为发布说明草稿；
- 本地预演如何生成 release notes；
- CI artifacts 中新增 release notes artifact。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_notes_builder.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_go_live_summary_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_analysis_rollout_decision_builder.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_rollout_summary_renderer.py tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_analysis_go_live_summary_builder.py tests/test_analysis_release_notes_builder.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
