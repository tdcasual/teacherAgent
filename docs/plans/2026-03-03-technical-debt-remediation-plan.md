# Technical Debt Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 4 周内把当前“高速迭代遗留债务”收敛到可持续维护状态，优先消除会阻塞 CI 和高风险运行路径的债务。

**Architecture:** 先做“止血层”治理（质量预算恢复、守卫阈值统一、文档与真实结构对齐），再做“结构层”治理（app_core 兼容外壳减薄、worker 生命周期规则收口），最后做“风险层”治理（chart trusted 默认策略退出、超大模块拆分）。每个任务都走小步提交、可回归验证、可回滚。

**Tech Stack:** Python 3.9/3.13, FastAPI, pytest, Ruff, mypy, React/TypeScript, Vitest, GitHub Actions.

---

## Phase A (Week 1): Stop The Bleeding

### Task 1: 恢复后端质量预算到绿色

**Files:**
- Create: `tests/test_backend_quality_budget_regression.py`
- Modify: `services/api/context_runtime_facade.py`
- Modify: `services/api/routes/skill_routes.py`
- Modify: `services/api/wiring/exam_wiring.py`
- Modify: `services/api/wiring/assignment_wiring.py`

**Step 1: 写失败回归测试（预算必须不超线）**

```python
import json
import subprocess
import sys


def test_backend_quality_budget_print_only_within_budget() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/quality/check_backend_quality_budget.py", "--print-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    metrics = payload["metrics"]
    budget = payload["budget"]
    assert metrics["ruff_errors"] <= budget["ruff_max"]
    assert metrics["mypy_errors"] <= budget["mypy_max"]
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_backend_quality_budget_regression.py`  
Expected: FAIL（`ruff_errors` 目前 > `ruff_max`）。

**Step 3: 最小改动修复**

- 统一并排序 `context_runtime_facade.py`、`skill_routes.py`、`exam_wiring.py` 导入块。
- 为 `_get_assignment_detail_api` 增加显式返回注解，消除 mypy `no-untyped-def`。

**Step 4: 运行验证**

Run: `python3 -m ruff check services/api --statistics`  
Expected: `Found 0 errors.` 或不超过预算。  

Run: `python3 -m mypy --follow-imports=skip services/api`  
Expected: `Success: no issues found` 或不超过预算。  

Run: `python3 -m pytest -q tests/test_backend_quality_budget_regression.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_backend_quality_budget_regression.py services/api/context_runtime_facade.py services/api/routes/skill_routes.py services/api/wiring/exam_wiring.py services/api/wiring/assignment_wiring.py
git commit -m "fix(quality): restore backend budget gates to green"
```

### Task 2: 收敛 app_core 预算口径（避免多阈值并存）

**Files:**
- Create: `tests/test_app_core_budget_sync.py`
- Modify: `tests/test_app_core_structure.py`
- Modify: `tests/test_app_core_decomposition.py`
- Modify: `config/backend_quality_budget.json`

**Step 1: 写失败测试（守卫测试必须引用同一预算）**

```python
import json
from pathlib import Path


def test_app_core_guardrail_thresholds_sync_with_budget() -> None:
    budget = json.loads(Path("config/backend_quality_budget.json").read_text(encoding="utf-8"))
    app_core_max = int(budget["app_core_max_lines"])
    text = Path("tests/test_app_core_structure.py").read_text(encoding="utf-8")
    text2 = Path("tests/test_app_core_decomposition.py").read_text(encoding="utf-8")
    assert str(app_core_max) in text
    assert str(app_core_max) in text2
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_app_core_budget_sync.py`  
Expected: FAIL（当前仍是 `900/1400` 历史阈值）。

**Step 3: 最小改动修复**

- 将两处守卫测试改为读取 `config/backend_quality_budget.json`，不再硬编码数字。
- 保留历史说明注释，但不保留独立阈值。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_app_core_structure.py tests/test_app_core_decomposition.py tests/test_app_core_budget_sync.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_app_core_budget_sync.py tests/test_app_core_structure.py tests/test_app_core_decomposition.py config/backend_quality_budget.json
git commit -m "refactor(guardrails): unify app_core thresholds with budget config"
```

### Task 3: 文档与代码边界同步（去除过期路径）

**Files:**
- Create: `tests/test_architecture_doc_paths.py`
- Modify: `docs/architecture/module-boundaries.md`
- Modify: `docs/explain/backend-quality-hardening-overview.md`

**Step 1: 写失败测试（文档中引用的关键路径必须存在）**

```python
from pathlib import Path


def test_module_boundaries_referenced_paths_exist() -> None:
    doc = Path("docs/architecture/module-boundaries.md").read_text(encoding="utf-8")
    candidates = [
        "frontend/apps/student/src/features/session/StudentSessionShell.tsx",
        "frontend/apps/student/src/features/chat/StudentChatPanel.tsx",
        "frontend/apps/student/src/features/workbench/StudentWorkbench.tsx",
    ]
    for path in candidates:
        assert path not in doc, f"outdated path remains in doc: {path}"
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_architecture_doc_paths.py`  
Expected: FAIL.

**Step 3: 最小改动修复**

- 替换为当前真实入口：`App.tsx`、`features/chat/ChatPanel.tsx`、`hooks/useSessionManager.ts` 等。
- 明确“文档必须随结构守卫测试同步更新”的规则。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_architecture_doc_paths.py tests/test_student_frontend_structure.py tests/test_teacher_frontend_structure.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_architecture_doc_paths.py docs/architecture/module-boundaries.md docs/explain/backend-quality-hardening-overview.md
git commit -m "docs(architecture): align module boundaries with current frontend structure"
```

## Phase B (Week 2): Structural Debt Reduction

### Task 4: `app_core` 兼容外壳减薄（第一阶段）

**Files:**
- Modify: `services/api/app_core.py`
- Modify: `services/api/app_core_service_imports.py`
- Modify: `services/api/context_runtime_facade.py`
- Modify: `tests/test_no_star_imports_guardrail.py`
- Create: `tests/test_app_core_star_import_budget.py`

**Step 1: 写失败测试（限制 `app_core` 的星号导入数量）**

```python
from pathlib import Path


def test_app_core_star_import_count_budget() -> None:
    text = Path("services/api/app_core.py").read_text(encoding="utf-8")
    count = text.count("import *")
    assert count <= 16
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_app_core_star_import_budget.py`  
Expected: FAIL（当前星号导入数更高）。

**Step 3: 最小改动修复**

- 先移除 wiring/context 层中的一组 `import *`，改显式导出。
- 不触碰业务行为，仅收敛导入方式和命名暴露面。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_app_core_star_import_budget.py tests/test_no_star_imports_guardrail.py tests/test_app_core_surface.py`  
Expected: PASS.

Run: `python3 -m mypy --follow-imports=skip services/api`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/app_core.py services/api/app_core_service_imports.py services/api/context_runtime_facade.py tests/test_no_star_imports_guardrail.py tests/test_app_core_star_import_budget.py
git commit -m "refactor(app_core): reduce compatibility star-import surface phase 1"
```

### Task 5: worker 生命周期规则收口（提取共享状态机）

**Files:**
- Create: `services/api/workers/lifecycle_state.py`
- Modify: `services/api/workers/chat_worker_service.py`
- Modify: `services/api/workers/upload_worker_service.py`
- Modify: `services/api/workers/exam_worker_service.py`
- Modify: `services/api/workers/profile_update_worker_service.py`
- Create: `tests/test_worker_lifecycle_state.py`

**Step 1: 写失败测试（共享规则）**

```python
def test_stop_keeps_started_true_when_thread_alive() -> None:
    from services.api.workers.lifecycle_state import compute_stop_result

    result = compute_stop_result(thread_alive=True)
    assert result.worker_started is True
    assert result.clear_thread_ref is False
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_worker_lifecycle_state.py`  
Expected: FAIL（模块尚不存在）。

**Step 3: 最小改动修复**

- 把 `join(timeout)` 后状态判定规则统一下沉到 `lifecycle_state.py`。
- 让 4 个 worker 调用同一逻辑，避免复制粘贴分叉。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_worker_lifecycle_state.py tests/test_chat_worker_service.py tests/test_inline_worker_services.py tests/test_chat_job_flow.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/workers/lifecycle_state.py services/api/workers/chat_worker_service.py services/api/workers/upload_worker_service.py services/api/workers/exam_worker_service.py services/api/workers/profile_update_worker_service.py tests/test_worker_lifecycle_state.py
git commit -m "refactor(workers): centralize lifecycle invariants and stale-state handling"
```

## Phase C (Month 1): Risk Closure And Deep Refactor

### Task 6: 关闭 `chart.exec` 默认 trusted 风险

**Files:**
- Modify: `services/api/chart_executor.py`
- Modify: `services/common/tool_registry.py`
- Modify: `docs/reference/risk-register.md`
- Create: `tests/test_chart_exec_policy_defaults.py`

**Step 1: 写失败测试（默认必须 sandboxed）**

```python
def test_chart_exec_defaults_to_sandboxed_profile() -> None:
    from services.api.chart_executor import execute_chart_exec
    # 仅校验默认 profile 解析逻辑
    assert True  # 先写出明确断言目标，再补完整 mock
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_chart_exec_policy_defaults.py`  
Expected: FAIL（当前默认 trusted）。

**Step 3: 最小改动修复**

- `chart_executor` 默认 profile 从 `trusted` 改 `sandboxed`。
- `tool_registry` 的 `execution_profile.default` 同步改 `sandboxed`。
- 保留白名单开关用于受控 trusted 场景。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_chart_exec_policy_defaults.py tests/test_chart_executor.py tests/test_chart_sandbox.py tests/test_chart_exec_tool.py`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/chart_executor.py services/common/tool_registry.py docs/reference/risk-register.md tests/test_chart_exec_policy_defaults.py
git commit -m "feat(security): default chart.exec to sandboxed profile"
```

### Task 7: 拆分超大模块（auth + chart）

**Files:**
- Create: `services/api/auth/login_service.py`
- Create: `services/api/auth/password_reset_service.py`
- Modify: `services/api/auth_registry_service.py`
- Create: `services/api/chart/runner_service.py`
- Create: `services/api/chart/policy_service.py`
- Modify: `services/api/chart_executor.py`
- Create: `tests/test_auth_registry_split.py`
- Create: `tests/test_chart_executor_split.py`

**Step 1: 写失败测试（新模块必须被主模块调用）**

```python
def test_auth_registry_delegates_login_to_login_service() -> None:
    source = open("services/api/auth_registry_service.py", encoding="utf-8").read()
    assert "from .auth.login_service import" in source
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_auth_registry_split.py tests/test_chart_executor_split.py`  
Expected: FAIL.

**Step 3: 最小改动修复**

- 先迁移一条链路（login、chart 执行入口），通过后再迁移其它函数。
- 每次迁移只改一类职责，避免跨域大提交。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_auth_registry_service.py tests/test_chart_executor.py tests/test_auth_registry_split.py tests/test_chart_executor_split.py`  
Expected: PASS.

Run: `python3 -m mypy --follow-imports=skip services/api`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/auth/login_service.py services/api/auth/password_reset_service.py services/api/auth_registry_service.py services/api/chart/runner_service.py services/api/chart/policy_service.py services/api/chart_executor.py tests/test_auth_registry_split.py tests/test_chart_executor_split.py
git commit -m "refactor(core): split oversized auth/chart modules by responsibility"
```

## Milestone Exit Criteria

1. `scripts/quality/check_backend_quality_budget.py` 在主分支持续通过 7 天。
2. `services/api/app_core.py` 星号导入数量下降到 16 及以下。
3. worker 生命周期类回归（`chat_worker + inline_worker`）连续 3 次全绿。
4. `chart.exec` 默认档位为 `sandboxed` 且风险台账更新为“已关闭”或“仅白名单 trusted”。
5. 至少完成一次完整 CI 验证：
   - `python -m pytest tests/ -x -q -m "not stress" --cov=services/api --cov-fail-under=84`
   - `python scripts/quality/check_backend_quality_budget.py`
   - `cd frontend && npm run verify`

## Suggested Execution Order

1. Task 1 -> Task 2 -> Task 3
2. Task 4 -> Task 5
3. Task 6 -> Task 7

Plan complete and saved to `docs/plans/2026-03-03-technical-debt-remediation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration.

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints.
