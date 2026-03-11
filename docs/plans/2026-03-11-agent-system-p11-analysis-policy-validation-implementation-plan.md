# Agent System P11 Analysis Policy Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 analysis policy 增加强 schema 校验、边界检查和独立质量门禁脚本，确保 `config/analysis_policy.json` 与临时 `--policy-config` 覆盖文件在进入发布门禁前就能 fail-fast。

**Architecture:** 保持 `config/analysis_policy.json` 作为统一真相源，不新增第二套配置格式。`services/api/analysis_policy_service.py` 负责 merge + validate + normalize，`scripts/quality/check_analysis_policy.py` 负责 CI / 本地门禁调用；现有 release-readiness、review drift、strategy eval 脚本继续只依赖 loader，不各自重复校验逻辑。

**Tech Stack:** Python 3.13、Pydantic v2、pytest、现有 `scripts/quality/*` 风格。

---

### Task 1: Add typed analysis policy validation in loader

**Files:**
- Modify: `services/api/analysis_policy_service.py`
- Modify: `tests/test_analysis_policy_service.py`

**Step 1: Write the failing test**

新增测试要求：
- `load_analysis_policy(...)` 对非法 rate、负数 count、无效 priority、空 edge-case tag 直接报错；
- merge 后缺失字段仍可由默认值补齐，但最终结果必须通过 schema；
- 校验后输出保持调用方当前依赖的 dict 结构。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 用 Pydantic model 表达三大 section：`release_readiness`、`review_feedback`、`strategy_eval`；
- 对 rates 做 `0..1` 校验、counts / window 做非负或正整数校验；
- 对 priority 做枚举校验，对 list/string 字段做非空归一化；
- `load_analysis_policy()` 在 merge 后统一调用 validate。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py`

Expected: PASS。

---

### Task 2: Add a standalone analysis policy quality gate script

**Files:**
- Create: `scripts/quality/check_analysis_policy.py`
- Create: `tests/test_analysis_policy_quality_gate.py`

**Step 1: Write the failing test**

新增测试要求：
- 默认仓库 policy 文件能通过 gate；
- 非法 policy 文件会返回非零退出码并输出明确失败信息；
- `--print-only` 只打印 summary，不阻断。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_quality_gate.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 复用 `analysis_policy_service` 的 loader/validator；
- 脚本输出可审计 summary，例如 threshold、reason spec 数量、required edge-case 数量；
- 保持与 `scripts/quality/check_backend_quality_budget.py` 类似的 CLI 风格。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_quality_gate.py`

Expected: PASS。

---

### Task 3: Wire docs and final verification

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Step 1: Update docs**

补充：
- policy 变更前的校验命令；
- CI / 本地质量门禁的推荐调用方式；
- 失败时的处理原则：先修 policy，再谈放量。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_replay_analysis_run.py tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py`

Expected: PASS。
