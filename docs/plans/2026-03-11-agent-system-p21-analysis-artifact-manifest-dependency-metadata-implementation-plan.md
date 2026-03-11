# Agent System P21 Analysis Artifact Manifest Dependency Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `analysis-artifact-manifest.json` 补充稳定的依赖关系与生成顺序元数据，方便后续自动归档、消费和完整性检查。

**Architecture:** 在现有 manifest builder 上增加受控静态元数据，而不重新设计 artifact 链。每个 artifact 记录 `build_order`、`depends_on`、`generated_by`，并在顶层输出 `build_sequence`，让下游工具可以不解析 CI workflow 也理解产物关系。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、JSON artifacts。

---

### Task 1: Add failing tests for manifest dependency metadata

**Files:**
- Modify: `tests/test_analysis_artifact_manifest_builder.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

覆盖以下行为：
- manifest 顶层输出 `build_sequence`；
- `analysis-release-notes.md` 条目包含稳定 `build_order`、`depends_on`、`generated_by`；
- `analysis-artifact-manifest.json` 条目也会声明自己依赖前置 artifacts。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement dependency metadata in manifest builder

**Files:**
- Modify: `scripts/quality/build_analysis_artifact_manifest.py`

**Step 1: Write minimal implementation**

- 为固定 artifact 列表增加 `build_order`、`depends_on`、`generated_by`；
- 顶层输出 `build_sequence`；
- 保持现有字段不变，避免破坏已存在消费者。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify broadly

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Update docs**

补充：
- manifest 中的 `build_order / depends_on / generated_by` 的用途；
- 本地预演时如何使用 manifest 判断 artifact 是否完整。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_release_notes_builder.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_rollout_summary_renderer.py tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_analysis_go_live_summary_builder.py tests/test_analysis_release_notes_builder.py tests/test_analysis_artifact_manifest_builder.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
