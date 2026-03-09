# Agent System P0 Stabilization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前 agent 系统从“已平台化但偏人工运维”提升到“可持续运营、可持续扩展、入口职责更清晰”的稳定 P0 状态。

**Architecture:** 继续坚持 `workflow-first`，不扩大 agent 自治范围。P0 仅补 4 类能力：前门协调器瘦身、metrics 持久化/导出、review drift 自动摘要、domain contract CI gate；不引入新的开放式 orchestration。

**Tech Stack:** Python 3.13、pytest、现有 `services/api` 应用层、GitHub Actions、现有 analysis runtime/report/review/metrics 组件。

---

### Task 1: 拆薄 `agent_service` 前门协调器

**Files:**
- Modify: `services/api/agent_service.py`
- Create: `services/api/agent_runtime_guards.py`
- Create: `services/api/agent_context_resolution_service.py`
- Test: `tests/test_agent_service.py`
- Test: `tests/test_analysis_followup_router.py`

**Step 1: Write the failing test**
- 新增测试要求：
  - `agent_service` 仅负责协调，不再直接承载 guard/context 细节
  - 考试总分/单科 guard 逻辑迁到新模块后行为不变
  - analysis follow-up 入口仍走 `/services/api/analysis_followup_router.py`

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_agent_service.py tests/test_analysis_followup_router.py`
- Expected: FAIL，失败点来自新抽取模块尚不存在或旧实现仍耦合在 `agent_service.py`

**Step 3: Write minimal implementation**
- 抽出“总分/单科 guard + exam context 预处理”到 `agent_runtime_guards.py`
- 抽出 “exam id / analysis target / context resolution” 到 `agent_context_resolution_service.py`
- `agent_service.py` 仅保留：
  - runtime deps 定义
  - 入口级 orchestration
  - 调用 follow-up router
  - 调用 guard/context helpers

**Step 4: Run test to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_agent_service.py tests/test_analysis_followup_router.py`
- Expected: PASS

**Step 5: Run neighboring tests**
- Run: `./.venv/bin/python -m pytest -q tests/test_skill_auto_router.py tests/test_chat_job_processing_service.py`
- Expected: PASS

### Task 2: 为 analysis metrics 增加持久化快照与导出

**Files:**
- Modify: `services/api/analysis_metrics_service.py`
- Create: `services/api/analysis_metrics_store.py`
- Modify: `services/api/routes/analysis_report_routes.py`
- Modify: `services/api/wiring/chat_wiring.py`
- Test: `tests/test_analysis_metrics_service.py`
- Create: `tests/test_analysis_metrics_store.py`
- Doc: `docs/operations/slo-and-observability.md`

**Step 1: Write the failing test**
- 新增测试要求：
  - metrics snapshot 可写入本地 store 并重新加载
  - 重启场景下 counters 不丢失
  - `/teacher/analysis/metrics` 返回持久化后的 snapshot
  - workflow routing metrics 也在持久化范围内

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_metrics_service.py tests/test_analysis_metrics_store.py tests/test_analysis_report_routes.py`
- Expected: FAIL

**Step 3: Write minimal implementation**
- 新建 `analysis_metrics_store.py`
- `AnalysisMetricsService` 增加 store 加载/保存能力
- 路由层仍只读 service，不直接管 IO

**Step 4: Run test to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_analysis_metrics_service.py tests/test_analysis_metrics_store.py tests/test_analysis_report_routes.py`
- Expected: PASS

### Task 3: 增加 review drift 自动摘要脚本

**Files:**
- Modify: `services/api/review_feedback_service.py`
- Create: `scripts/build_review_drift_report.py`
- Modify: `scripts/analysis_strategy_eval.py`
- Test: `tests/test_review_feedback_service.py`
- Create: `tests/test_review_drift_report.py`
- Test: `tests/test_analysis_strategy_eval.py`
- Doc: `docs/operations/change-management-and-governance.md`

### Task 4: 把 analysis domain contract checker 接进 CI gate

**Files:**
- Modify: `scripts/check_analysis_domain_contract.py`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_architecture_doc_paths.py`
- Create: `tests/test_analysis_domain_contract_checker.py`
- Doc: `docs/reference/analysis-domain-onboarding-template.md`
- Doc: `docs/reference/analysis-domain-checklist.md`

### Task 5: P0 集成回归与发布门禁

**Files:**
- Reference: `services/api/agent_service.py`
- Reference: `services/api/analysis_metrics_service.py`
- Reference: `services/api/review_feedback_service.py`
- Reference: `scripts/check_analysis_domain_contract.py`
- Reference: `.github/workflows/ci.yml`
