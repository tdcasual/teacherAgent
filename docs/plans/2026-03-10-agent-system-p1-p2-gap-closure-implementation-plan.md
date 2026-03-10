# Agent System P1 P2 Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前已具备基础 P1/P2 能力的 agent 系统，补齐“可持续灰度运营”和“接入工业化”剩余缺口：批量 shadow compare、release-readiness 汇总、domain capability matrix。

**Architecture:** 不重复实现已经存在的 review feedback、controlled job graph、replay/compare 单对比与 onboarding 模板，而是在这些已有能力之上补运营收口层。新增能力统一以脚本和只读聚合报告形式落地，不改变现有 analysis runtime 真相面。

**Tech Stack:** Python 3.13、pytest、现有 `scripts/compare_analysis_runs.py`、`scripts/replay_analysis_run.py`、`services/api/review_feedback_service.py`、manifest/binding registry、现有 docs/operations 与 docs/reference。

---

### Task 1: Batch shadow compare report

**Files:**
- Create: `scripts/build_analysis_shadow_compare_report.py`
- Test: `tests/test_analysis_shadow_compare_report.py`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 1: Write the failing test**

新增测试要求：
- 能按相同文件名批量配对 baseline/candidate report detail；
- 输出 `total_pairs`、`changed_pairs`、`changed_ratio`；
- 输出 `pairs[].report_id`、`pairs[].domain`、`pairs[].changed`；
- 输出 `top_changed_reports` 聚合，便于 shadow compare 复盘。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_shadow_compare_report.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 复用 `scripts/compare_analysis_runs.py`；
- 只支持“按同名文件配对”的最小批处理模式；
- 输出稳定 JSON 结构；
- 缺失配对文件时 fail-fast。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_shadow_compare_report.py tests/test_replay_analysis_run.py`

Expected: PASS。

---

### Task 2: Release-readiness aggregation report

**Files:**
- Create: `scripts/build_analysis_release_readiness_report.py`
- Test: `tests/test_analysis_release_readiness_report.py`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Doc: `docs/operations/change-management-and-governance.md`

**Step 1: Write the failing test**

新增测试要求：
- 读取 contract check、metrics snapshot、review drift summary、shadow compare summary；
- 输出 `ready_for_release`、`blocking_issues`、`warnings`；
- 当 contract check 失败、invalid_output 激增、changed_ratio 超阈值时阻断发布。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_readiness_report.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 只做只读聚合，不写系统状态；
- 默认阈值写在脚本内，支持 CLI 覆盖；
- 输出结构化 JSON，便于后续接 dashboard/automation。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_readiness_report.py tests/test_analysis_domain_contract_checker.py tests/test_analysis_metrics_service.py tests/test_review_feedback_service.py`

Expected: PASS。

---

### Task 3: Export domain capability matrix

**Files:**
- Create: `scripts/export_analysis_domain_capability_matrix.py`
- Create: `docs/reference/analysis-domain-capability-matrix.md`
- Test: `tests/test_analysis_domain_capability_matrix.py`
- Modify: `docs/INDEX.md`
- Modify: `docs/reference/analysis-domain-onboarding-template.md`
- Modify: `docs/reference/analysis-domain-checklist.md`

**Step 1: Write the failing test**

新增测试要求：
- capability matrix 至少列出 `domain_id`、`rollout_stage`、`strategy_ids`、`specialist_ids`、`has_runtime_binding`、`has_report_binding`、`has_replay_compare_support`；
- 文档进入 `docs/INDEX.md`；
- matrix 可由脚本从 manifest/binding registry 生成。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_domain_capability_matrix.py tests/test_architecture_doc_paths.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 复用 `scripts/check_analysis_domain_contract.py` 的领域元数据；
- 生成 Markdown matrix 文档；
- 明确这是 onboarding / extension 入口之一。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_domain_capability_matrix.py tests/test_architecture_doc_paths.py tests/test_analysis_domain_contract_checker.py`

Expected: PASS。

---

### Task 4: P1/P2 final regression

**Files:**
- Reference: `scripts/build_analysis_shadow_compare_report.py`
- Reference: `scripts/build_analysis_release_readiness_report.py`
- Reference: `scripts/export_analysis_domain_capability_matrix.py`

**Step 1: Run focused regression**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_shadow_compare_report.py tests/test_analysis_release_readiness_report.py tests/test_analysis_domain_capability_matrix.py tests/test_analysis_domain_contract_checker.py tests/test_review_feedback_service.py tests/test_analysis_strategy_eval.py tests/test_replay_analysis_run.py tests/test_architecture_doc_paths.py`

Expected: PASS。

**Step 2: Run existing neighboring regression**

Run: `./.venv/bin/python -m pytest -q tests/test_specialist_job_graph_runtime.py tests/test_review_feedback_service.py tests/test_replay_analysis_run.py tests/test_analysis_report_service.py tests/test_analysis_domain_contract_checker.py`

Expected: PASS。

**Step 3: Run scripts manually**

Run: `./.venv/bin/python scripts/build_analysis_shadow_compare_report.py --help`
Run: `./.venv/bin/python scripts/build_analysis_release_readiness_report.py --help`
Run: `./.venv/bin/python scripts/export_analysis_domain_capability_matrix.py --output docs/reference/analysis-domain-capability-matrix.md`

Expected: exit 0。
