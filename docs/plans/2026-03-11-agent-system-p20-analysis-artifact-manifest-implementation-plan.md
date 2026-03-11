# Agent System P20 Analysis Artifact Manifest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 analysis rollout artifacts 生成统一的 `analysis-artifact-manifest.json`，把 policy / preflight / decision / brief / go-live summary / release notes 等产物编目成稳定的机器可读索引。

**Architecture:** 复用现有 `analysis-artifacts/` 目录中的已知文件名，新增一个轻量 manifest builder 输出统一 JSON 索引。CI 在 upload artifact 前生成 manifest；本地也可直接运行同一脚本，方便发布记录、自动消费和归档检查。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、JSON artifacts、GitHub Actions。

---

### Task 1: Add failing tests for artifact manifest

**Files:**
- Create: `tests/test_analysis_artifact_manifest_builder.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

覆盖以下行为：
- manifest builder 会编目已知 artifacts，至少包含 `analysis-policy.json`、`analysis-preflight.json`、`analysis-rollout-decision.json`、`analysis-rollout-brief.md`、`analysis-go-live-summary.md`、`analysis-release-notes.md`；
- 每个 artifact 记录 `path`、`exists`、`format`、`artifact_type`；
- CI workflow 会生成 `analysis-artifact-manifest.json`。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement manifest builder and wire CI

**Files:**
- Create: `scripts/quality/build_analysis_artifact_manifest.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write minimal implementation**

- 扫描固定 artifact 名单并生成 `analysis-artifact-manifest.json`；
- manifest 至少输出：`generated_at`、`artifact_dir`、`artifact_count`、`artifacts[]`；
- `artifacts[]` 内至少包含：`name`、`path`、`exists`、`format`、`artifact_type`；
- CI 在 upload artifact 前生成 manifest 文件。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify broadly

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Update docs**

补充：
- `analysis-artifact-manifest.json` 的用途与字段语义；
- 本地预演如何生成 manifest；
- CI artifacts 中新增 manifest artifact。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_release_notes_builder.py tests/test_analysis_go_live_summary_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_analysis_rollout_decision_builder.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_rollout_summary_renderer.py tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_analysis_go_live_summary_builder.py tests/test_analysis_release_notes_builder.py tests/test_analysis_artifact_manifest_builder.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
