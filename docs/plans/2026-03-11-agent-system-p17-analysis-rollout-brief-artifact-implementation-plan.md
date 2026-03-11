# Agent System P17 Analysis Rollout Brief Artifact Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于现有 analysis policy / preflight / decision artifacts 生成一个可归档、可附到发布记录中的 markdown rollout brief。

**Architecture:** 复用 `analysis-policy.json`、`analysis-preflight.json` 与 `analysis-rollout-decision.json`，新增一个轻量 markdown builder 输出 `analysis-rollout-brief.md`。CI 生成 brief artifact 并与其他 analysis artifacts 一起上传；本地也可直接运行同一脚本生成 release/go-live 简报草稿。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、Markdown/JSON artifacts、GitHub Actions。

---

### Task 1: Add failing tests for rollout brief artifact

**Files:**
- Create: `tests/test_analysis_rollout_brief_builder.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

覆盖以下行为：
- brief builder 能读取 decision/policy/preflight artifacts，输出包含 decision、policy status、blocking issue count、top owners、recommended actions 的 markdown；
- CI workflow 会生成 `analysis-rollout-brief.md`。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_brief_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement brief builder and wire CI

**Files:**
- Create: `scripts/quality/build_analysis_rollout_brief.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write minimal implementation**

- 读取 `analysis-policy.json`、`analysis-preflight.json`、`analysis-rollout-decision.json`；
- 输出 `analysis-rollout-brief.md`，至少包含：`Decision`、`Policy`、`Preflight`、`Top Owners`、`Recommended Actions`；
- 若某些 artifacts 缺失，brief 仍输出可读 fallback；
- CI 在 upload artifact 前生成 brief 文件。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_brief_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify broadly

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Update docs**

补充：
- `analysis-rollout-brief.md` 可作为发布记录 / go-live summary 草稿；
- 本地预演如何生成 brief；
- CI artifacts 中新增 brief artifact。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_brief_builder.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_summary_renderer.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_rollout_summary_renderer.py tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
