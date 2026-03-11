# Agent System P22 Analysis Artifact Integrity Checker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 analysis artifact 链补上独立的完整性校验 gate，在 CI 发布 summary 与上传 artifact 前，就能发现 manifest 依赖错误、生成顺序漂移和磁盘缺件。

**Architecture:** 保持 `build_analysis_artifact_manifest.py` 只负责声明与快照，不把失败逻辑塞回 builder。本任务新增独立脚本 `scripts/quality/check_analysis_artifact_integrity.py`，直接消费 `analysis-artifact-manifest.json` 并输出结构化 JSON 结果，供 CI、本地预演和后续发布自动化复用。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、JSON artifacts、GitHub Actions。

---

### Task 1: Add failing integrity checker tests

**Files:**
- Create: `tests/test_analysis_artifact_integrity_checker.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing tests**

覆盖以下行为：
- manifest 完整且磁盘产物齐全时，checker 返回 `ok=true` 且 exit code 为 `0`；
- `depends_on` 引用未知 artifact 时，checker 返回结构化 `unknown_dependency` 问题并非零退出；
- `build_sequence` 与 `build_order` 不一致时，checker 返回 `build_sequence_mismatch`；
- artifact 名称重复或依赖文件缺失时，checker 能给出稳定 reason code；
- CI workflow 在 manifest 之后、summary/upload 之前运行 integrity checker。

**Step 2: Run tests to verify red**

Run: `./.venv-p15/bin/python -m pytest -q tests/test_analysis_artifact_integrity_checker.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement the integrity checker

**Files:**
- Create: `scripts/quality/check_analysis_artifact_integrity.py`

**Step 1: Implement minimal checker**

- 读取 manifest JSON，并验证顶层字段与 artifact 条目结构；
- 检查 artifact 名称唯一、`build_sequence` 可映射到所有 artifact；
- 检查 `depends_on` 全都存在于 manifest，且依赖的 `build_order` 必须早于当前 artifact；
- 检查 manifest 中标记存在的 artifact 在磁盘上真实存在，且若某 artifact 存在，其依赖文件也必须存在；
- 输出 `ok`、`issue_count`、`issues`、`validated_artifacts`、`artifact_dir` 等结构化 JSON；
- integrity 失败时返回非零 exit code。

**Step 2: Run tests to verify green**

Run: `./.venv-p15/bin/python -m pytest -q tests/test_analysis_artifact_integrity_checker.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Wire CI and docs, then verify broadly

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 1: Wire the checker**

- 在 manifest 生成之后运行 integrity checker；
- 确保 summary 渲染与 artifact upload 只能消费通过完整性校验的 artifact 链。

**Step 2: Update docs**

补充：
- integrity checker 的目的、输入与输出；
- 本地预演如何先 build manifest、再 run integrity checker；
- rollout checklist 中把 integrity gate 变成发布前必做项。

**Step 3: Run focused verification**

Run: `./.venv-p15/bin/python -m pytest -q tests/test_analysis_artifact_integrity_checker.py tests/test_analysis_artifact_manifest_builder.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_release_notes_builder.py`

Expected: PASS。

**Step 4: Run broader verification**

Run: `./.venv-p15/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_analysis_rollout_summary_renderer.py tests/test_analysis_rollout_decision_builder.py tests/test_analysis_rollout_brief_builder.py tests/test_analysis_go_live_summary_builder.py tests/test_analysis_release_notes_builder.py tests/test_analysis_artifact_manifest_builder.py tests/test_analysis_artifact_integrity_checker.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
