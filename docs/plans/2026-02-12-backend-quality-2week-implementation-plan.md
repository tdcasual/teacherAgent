# Backend Quality Hardening (2 Weeks) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 2 周内把后端从“功能可用但质量债高”提升到“可持续迭代”，重点降低静态错误、缩小组合根、提高 CI 门禁可信度。

**Architecture:** 采用“先门禁再重构”的路线。先用测试与 CI 固化质量底线，再按高风险模块（`app_core`、`llm_routing*`、`teacher_provider_registry_service`）分批做小步重构，每个变更都走 TDD 与小提交，避免大爆炸。

**Tech Stack:** Python 3.13, FastAPI, Pytest, Ruff, Mypy, GitHub Actions, 文件型存储与 RQ/Inline 队列。

---

## Two-Week Milestones

- **Week 1 里程碑：** CI 门禁补齐 + 2 个高风险模块降债（星号导入、类型问题）。
- **Week 2 里程碑：** `app_core` 第一阶段瘦身 + 生产安全策略收紧 + 质量报告落地。

## Exit Criteria (Day 10)

1. `python3 -m ruff check services/api --statistics` 总问题数相对基线下降 **>= 30%**。
2. `python3 -m mypy --follow-imports=skip services/api` 总错误数相对基线下降 **>= 35%**。
3. `services/api/app_core.py` 行数从约 `700` 降到 **<= 500**。
4. CI `backend-quality` job 新增 guardrails 测试并稳定通过。
5. 所有新增门禁测试在本地与 CI 均通过。

---

### Task 1: 建立质量基线与预算文件（Day 1）

**Files:**
- Create: `config/backend_quality_budget.json`
- Create: `scripts/quality/collect_backend_quality.sh`
- Create: `tests/test_backend_quality_budget.py`

**Step 1: Write the failing test**

```python
# tests/test_backend_quality_budget.py
from __future__ import annotations

import json
from pathlib import Path


def test_backend_quality_budget_file_exists_and_has_keys() -> None:
    path = Path("config/backend_quality_budget.json")
    assert path.exists(), "missing quality budget file"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("ruff_max", "mypy_max", "app_core_max_lines"):
        assert key in data, f"missing key: {key}"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_backend_quality_budget.py`
Expected: FAIL (`missing quality budget file`)

**Step 3: Write minimal implementation**

```json
{
  "ruff_max": 745,
  "mypy_max": 482,
  "app_core_max_lines": 700
}
```

```bash
# scripts/quality/collect_backend_quality.sh
#!/usr/bin/env bash
set -euo pipefail
python3 -m ruff check services/api --statistics || true
python3 -m mypy --follow-imports=skip services/api || true
wc -l services/api/app_core.py
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_backend_quality_budget.py`
Expected: PASS

**Step 5: Commit**

```bash
git add config/backend_quality_budget.json scripts/quality/collect_backend_quality.sh tests/test_backend_quality_budget.py
git commit -m "chore(quality): add backend quality baseline budget"
```

---

### Task 2: 补齐门禁测试（重复路由 + 星号导入约束）（Day 1-2）

**Files:**
- Create: `tests/test_no_star_imports_guardrail.py`
- Modify: `tests/test_no_duplicate_route_files.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write the failing test**

```python
# tests/test_no_star_imports_guardrail.py
from __future__ import annotations

from pathlib import Path

ALLOWED = {
    "services/api/app_core.py",
}


def test_no_star_imports_outside_allowlist() -> None:
    offenders: list[str] = []
    for path in Path("services/api").rglob("*.py"):
        rel = str(path).replace("\\", "/")
        if rel in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "import *" in text:
            offenders.append(rel)
    assert offenders == [], f"star imports not allowed: {offenders}"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_no_star_imports_guardrail.py`
Expected: FAIL（当前 `llm_routing.py`、`teacher_memory_core.py` 等会触发）

**Step 3: Write minimal implementation**
- 先不改业务逻辑，仅把 `tests/test_no_duplicate_route_files.py` 和新测试加入 CI guardrails。
- 更新 `.github/workflows/ci.yml` 的 `Run maintainability guardrails` 命令列表。

**Step 4: Run test to verify it passes (for CI wiring only)**

Run: `python3 -m pytest -q tests/test_no_duplicate_route_files.py`
Expected: PASS

Run: `python3 -m pytest -q tests/test_no_star_imports_guardrail.py`
Expected: 仍 FAIL（为后续 Task 3 提供 Red）

**Step 5: Commit**

```bash
git add tests/test_no_star_imports_guardrail.py tests/test_no_duplicate_route_files.py .github/workflows/ci.yml
git commit -m "test(guardrails): enforce no duplicate routes and star import policy"
```

---

### Task 3: 移除 `llm_routing*` 的星号导入并保持行为不变（Day 2-3）

**Files:**
- Modify: `services/api/llm_routing.py`
- Modify: `services/api/llm_routing_resolver.py`
- Modify: `tests/test_llm_routing_resolver.py`
- Test: `tests/test_no_star_imports_guardrail.py`

**Step 1: Write the failing test**
- 使用 Task 2 的 guardrail，确保当前为失败状态（Red）。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_no_star_imports_guardrail.py -k llm_routing`
Expected: FAIL

**Step 3: Write minimal implementation**
- 将 `services/api/llm_routing.py` 中 `from .llm_routing_resolver import *` 和 `from .llm_routing_proposals import *` 改为显式导入。
- 保持公开 API 不变（需要时用 `__all__` 明确导出符号）。

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/test_llm_routing_resolver.py tests/test_teacher_llm_routing_service.py tests/test_no_star_imports_guardrail.py`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/llm_routing.py services/api/llm_routing_resolver.py tests/test_llm_routing_resolver.py tests/test_no_star_imports_guardrail.py
git commit -m "refactor(routing): replace star imports with explicit exports"
```

---

### Task 4: 修复 `teacher_provider_registry_service` 的高频 Mypy 错误（Day 3-4）

**Files:**
- Modify: `services/api/teacher_provider_registry_service.py`
- Modify: `tests/test_teacher_provider_registry_routes.py` (or nearest existing provider-registry tests)

**Step 1: Write the failing test**

```python
# Add one focused test that passes malformed/None config payload
# and asserts graceful fallback instead of attribute errors.
def test_provider_registry_handles_none_nested_config() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_teacher_provider_registry_routes.py -k none_nested_config`
Expected: FAIL（若测试文件名不同，创建同名新测试文件）

**Step 3: Write minimal implementation**
- 增加 `_as_dict(value: Any) -> dict[str, Any]` 辅助函数。
- 在 `.get()` 链前统一做 `dict` 收敛，移除 `union-attr`。

**Step 4: Run target verification**

Run: `python3 -m mypy --follow-imports=skip services/api/teacher_provider_registry_service.py`
Expected: 错误显著下降或清零

Run: `python3 -m pytest -q tests/test_teacher_provider_registry_routes.py`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/teacher_provider_registry_service.py tests/test_teacher_provider_registry_routes.py
git commit -m "fix(types): harden provider registry nested config parsing"
```

---

### Task 5: `app_core` 第一阶段瘦身（拆出并发与限流辅助）（Day 5-6）

**Files:**
- Create: `services/api/chat_limits.py`
- Modify: `services/api/app_core.py`
- Create: `tests/test_chat_limits.py`

**Step 1: Write the failing test**

```python
# tests/test_chat_limits.py
from __future__ import annotations

from services.api.chat_limits import trim_messages


def test_trim_messages_respects_student_limit() -> None:
    messages = [{"role": "user", "content": str(i)} for i in range(100)]
    out = trim_messages(messages, role_hint="student", max_messages=40, max_chars=2000)
    assert len(out) == 40
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_chat_limits.py`
Expected: FAIL（模块/函数未定义）

**Step 3: Write minimal implementation**
- 在新模块实现：
  - `trim_messages(...)`
  - `student_inflight_guard(...)`
  - `acquire_limiters(...)`（迁移 `_limit`）
- `app_core.py` 仅调用新模块接口。

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/test_chat_limits.py tests/test_chat_route_flow.py tests/test_chat_start_flow.py`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/chat_limits.py services/api/app_core.py tests/test_chat_limits.py
git commit -m "refactor(app_core): extract chat concurrency/trim helpers"
```

---

### Task 6: CI 扩圈（Mypy + Ruff 分阶段覆盖）（Day 7）

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `config/backend_quality_budget.json`

**Step 1: Write the failing test**

```python
# tests/test_ci_backend_scope.py
from __future__ import annotations

from pathlib import Path


def test_ci_includes_new_backend_quality_targets() -> None:
    yml = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "services/api/llm_routing.py" in yml
    assert "services/api/teacher_provider_registry_service.py" in yml
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_ci_backend_scope.py`
Expected: FAIL

**Step 3: Write minimal implementation**
- 在 CI 的 mypy gate 先增加：
  - `services/api/llm_routing.py`
  - `services/api/teacher_provider_registry_service.py`
- ruff gate 先扩到 `services/api/routes`。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest -q tests/test_ci_backend_scope.py tests/test_ci_workflow_quality.py`
Expected: PASS

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml tests/test_ci_backend_scope.py config/backend_quality_budget.json
git commit -m "ci(backend): expand static quality gate scope"
```

---

### Task 7: 生产安全策略收紧（Auth Secret + 队列降级策略）（Day 8-9）

**Files:**
- Modify: `services/api/auth_service.py`
- Modify: `services/api/queue/queue_backend_factory.py`
- Modify: `services/api/settings.py`
- Modify: `tests/test_security_auth_hardening.py`
- Modify: `tests/test_queue_backend_factory.py`

**Step 1: Write the failing test**

```python
# tests/test_security_auth_hardening.py
def test_auth_required_true_without_secret_raises_startup_error(monkeypatch):
    ...

# tests/test_queue_backend_factory.py
def test_prod_mode_does_not_fallback_to_inline_backend(monkeypatch):
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_security_auth_hardening.py tests/test_queue_backend_factory.py -k "startup_error or prod_mode"`
Expected: FAIL

**Step 3: Write minimal implementation**
- `auth_service`：当 `AUTH_REQUIRED=1` 且 `AUTH_TOKEN_SECRET` 为空时抛出明确错误（仅生产模式强制）。
- `queue_backend_factory`：增加 `ALLOW_INLINE_FALLBACK_IN_PROD` 开关，默认禁止生产静默降级。

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/test_security_auth_hardening.py tests/test_queue_backend_factory.py tests/test_tenant_admin_and_dispatcher.py`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/auth_service.py services/api/queue/queue_backend_factory.py services/api/settings.py tests/test_security_auth_hardening.py tests/test_queue_backend_factory.py
git commit -m "security(runtime): harden auth secret and prod queue fallback policy"
```

---

### Task 8: 终验与报告（Day 10）

**Files:**
- Create: `docs/plans/2026-02-22-backend-quality-hardening-report.md`
- Modify: `config/backend_quality_budget.json`

**Step 1: Write the failing test**

```python
# tests/test_backend_quality_budget.py
# Add assertion that budget numbers are lower than baseline.
def test_quality_budget_is_tightened() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q tests/test_backend_quality_budget.py -k tightened`
Expected: FAIL

**Step 3: Write minimal implementation**
- 运行并记录：
  - `python3 -m ruff check services/api --statistics`
  - `python3 -m mypy --follow-imports=skip services/api`
  - `python3 -m pytest -q`（至少包含 CI backend-quality 相关测试集合）
- 将新指标写入 `backend_quality_budget.json`。
- 输出报告包含：基线 vs 当前、已解决问题、残留风险、下阶段计划。

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/test_backend_quality_budget.py`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/plans/2026-02-22-backend-quality-hardening-report.md config/backend_quality_budget.json tests/test_backend_quality_budget.py
git commit -m "docs(quality): publish 2-week backend hardening report"
```

---

## Daily Checklist (Operator View)

- Day 1: Task 1 + Task 2（门禁与基线）
- Day 2-3: Task 3（routing 星号导入清理）
- Day 3-4: Task 4（provider registry 类型收敛）
- Day 5-6: Task 5（app_core 第一阶段瘦身）
- Day 7: Task 6（CI 扩圈）
- Day 8-9: Task 7（生产安全策略）
- Day 10: Task 8（终验与报告）

## Verification Commands (Run Fresh Before Any “Done” Claim)

```bash
python3 -m ruff check services/api
python3 -m mypy --follow-imports=skip services/api
python3 -m pytest -q tests/test_app_core_surface.py tests/test_chat_routes.py tests/test_exam_routes.py tests/test_student_routes.py tests/test_docs_architecture_presence.py tests/test_refactor_report.py tests/test_auth_service.py tests/test_teacher_memory_core.py tests/test_chat_job_state_machine.py tests/test_rate_limit.py
python3 -m pytest -q tests/test_app_core_structure.py tests/test_app_core_import_fanout.py tests/test_assignment_wiring_structure.py tests/test_chat_wiring_structure.py tests/test_exam_wiring_structure.py tests/test_misc_wiring_structure.py tests/test_teacher_student_wiring_structure.py tests/test_worker_skill_wiring_structure.py tests/test_teacher_frontend_structure.py tests/test_tech_debt_targets.py tests/test_observability_store.py tests/test_operability_evidence.py
```

