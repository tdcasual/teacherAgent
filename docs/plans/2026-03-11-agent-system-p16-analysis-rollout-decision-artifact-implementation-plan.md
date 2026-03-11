# Agent System P16 Analysis Rollout Decision Artifact Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 analysis policy / preflight / ownership 输出收束为一个可归档、可本地复现、可供 CI 与发布记录复用的结构化放量结论 artifact。

**Architecture:** 复用现有 `analysis-policy.json`、`analysis-preflight.json` 与 `ownership_summary`，新增一个轻量 decision builder 输出 `analysis-rollout-decision.json`。CI 先生成 decision artifact，再由 summary renderer 消费它；本地也可以直接运行同一脚本，避免“结论只存在于 GitHub summary 文本里”。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、GitHub Actions、Markdown/JSON artifacts。

---

### Task 1: Add failing tests for rollout decision artifact

**Files:**
- Create: `tests/test_analysis_rollout_decision_builder.py`
- Modify: `tests/test_analysis_rollout_summary_renderer.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

覆盖以下行为：
- 当 preflight `ok=true` 且无 blocking issues 时，decision builder 输出 `go_for_controlled_rollout`；
- 当 preflight 有 blocking issues 时，输出 `blocked`，并带出 top owners / recommended actions；
- CI workflow 会生成 `analysis-rollout-decision.json`；
- summary renderer 若存在 decision artifact，会显示 decision / rationale。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_summary_renderer.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement decision builder and wire CI

**Files:**
- Create: `scripts/quality/build_analysis_rollout_decision.py`
- Modify: `scripts/quality/render_analysis_rollout_summary.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write minimal implementation**

- decision builder 读取 `analysis-policy.json` / `analysis-preflight.json`；
- 输出 `analysis-rollout-decision.json`，至少包含：`decision`、`decision_label`、`ready_for_rollout`、`summary`、`top_owners`、`recommended_actions`；
- 规则保持简单：无 blocking issues -> `go_for_controlled_rollout`，否则 `blocked`；
- summary renderer 若发现 decision artifact，则优先展示 decision 与 rationale；
- CI 在 summary step 前生成 decision artifact，并与其他 analysis artifacts 一起上传。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_summary_renderer.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify broadly

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 1: Update docs**

补充：
- `analysis-rollout-decision.json` 的用途与字段语义；
- 发布记录 / 本地预演如何使用该 artifact；
- CI artifacts 中新增 decision artifact。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_summary_renderer.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_preflight_gate.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_rollout_summary_renderer.py tests/test_analysis_rollout_decision_builder.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
