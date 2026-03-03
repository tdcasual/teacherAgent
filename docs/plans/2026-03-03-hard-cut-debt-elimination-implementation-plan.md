# Hard-Cut Debt Elimination Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不保留任何兼容层的前提下，最大化清除历史包袱、无效代码与文档漂移，把平台收敛到干净、健壮、解耦、可扩展的最小稳定架构。

**Architecture:** 采用三段式硬切策略：P0 先删除已确认无价值残留并修正文档真相；P1 拆除兼容壳（动态装载、`app_core` re-export facade、if-else 分发大函数）；P2 用质量闸门固化新边界（复杂度、异常策略、技能来源、测试范围）。全程 TDD，小步提交，可回滚。

**Tech Stack:** Python 3.13, FastAPI, pytest, Ruff, mypy, React + TypeScript, Playwright, GitHub Actions.

---

## Phase P0 (Day 1): Immediate Hard Deletions

### Task 1: Remove Go runtime residue and restore guardrail pass

**Files:**
- Delete: legacy Go-only compose override file in repo root
- Verify: `tests/test_no_go_artifacts.py`

**Step 1: Run failing guardrail test**

Run: `python3 -m pytest -q tests/test_no_go_artifacts.py`
Expected: FAIL, message contains stale Go artifact path assertion.

**Step 2: Delete the stale file**

Run: `rm -f <legacy-go-compose-override>`

**Step 3: Re-run guardrail**

Run: `python3 -m pytest -q tests/test_no_go_artifacts.py`
Expected: PASS.

**Step 4: Commit**

```bash
git add -A
git commit -m "chore(cleanup): remove stale go-exclusive compose residue"
```

### Task 2: Remove obsolete persona/routing E2E scenarios

**Files:**
- Delete: `frontend/e2e/student-persona-cards.spec.ts`
- Delete: `frontend/e2e/teacher-routing-provider.spec.ts`
- Create: `tests/test_e2e_scope_guard.py`

**Step 1: Add a failing guard test**

```python
from pathlib import Path

def test_removed_e2e_specs_absent() -> None:
    root = Path(__file__).resolve().parent.parent
    assert not (root / "frontend/e2e/student-persona-cards.spec.ts").exists()
    assert not (root / "frontend/e2e/teacher-routing-provider.spec.ts").exists()
```

**Step 2: Run test to confirm failure**

Run: `python3 -m pytest -q tests/test_e2e_scope_guard.py`
Expected: FAIL.

**Step 3: Delete obsolete E2E files**

Run:
```bash
rm -f frontend/e2e/student-persona-cards.spec.ts frontend/e2e/teacher-routing-provider.spec.ts
```

**Step 4: Verify test list no longer includes removed cases**

Run:
```bash
cd frontend
npx playwright test --list -c playwright.teacher.config.ts | rg "routing-provider|persona-cards" || true
```
Expected: no matched output.

Run: `cd .. && python3 -m pytest -q tests/test_e2e_scope_guard.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_e2e_scope_guard.py frontend/e2e
git commit -m "chore(e2e): remove obsolete persona/routing scenarios"
```

### Task 3: Fix HTTP API doc drift against actual route surface

**Files:**
- Modify: `docs/http_api.md`
- Create: `tests/test_http_api_doc_contract.py`
- Verify route sources: `services/api/routes/teacher_*_routes.py`

**Step 1: Add failing doc-contract test**

```python
from pathlib import Path

def test_http_api_doc_has_no_removed_teacher_routing_endpoints() -> None:
    text = Path("docs/http_api.md").read_text(encoding="utf-8")
    assert "/teacher/llm-routing" not in text

def test_http_api_doc_no_missing_service_paths() -> None:
    text = Path("docs/http_api.md").read_text(encoding="utf-8")
    stale = [
        "services/api/exam_api_service.py",
        "services/api/assignment_api_service.py",
        "services/api/student_profile_api_service.py",
        "services/api/teacher_routing_api_service.py",
    ]
    for path in stale:
        assert path not in text
```

**Step 2: Run test to confirm failure**

Run: `python3 -m pytest -q tests/test_http_api_doc_contract.py`
Expected: FAIL.

**Step 3: Update doc to current truth**

- 删除 `/teacher/llm-routing*` 章节。
- 删除不存在的 service 文件路径列表。
- 补充当前实际接口：`/teacher/model-config`、`/teacher/provider-registry*`。
- 明确路由聚合入口为 `services/api/app_routes.py` + `services/api/routes/*`。

**Step 4: Verify**

Run:
```bash
python3 -m pytest -q tests/test_http_api_doc_contract.py
python3 -m pytest -q tests/test_architecture_doc_paths.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/http_api.md tests/test_http_api_doc_contract.py
git commit -m "docs(api): align http api doc with real teacher route surface"
```

### Task 4: Remove dead routing CSS tokens in teacher app

**Files:**
- Modify: `frontend/apps/teacher/src/tailwind.css`
- Modify: `tests/test_teacher_frontend_structure.py`

**Step 1: Add failing guard in existing teacher structure test**

Add assertion:

```python
def test_teacher_css_has_no_routing_tokens() -> None:
    css = (
        Path(__file__).resolve().parent.parent
        / "frontend/apps/teacher/src/tailwind.css"
    ).read_text(encoding="utf-8")
    assert ".routing-" not in css
```

**Step 2: Run to confirm failure**

Run: `python3 -m pytest -q tests/test_teacher_frontend_structure.py`
Expected: FAIL.

**Step 3: Delete dead selectors**

Remove stale selectors:
- `.routing-grid`
- `.routing-proposal-json`

**Step 4: Verify**

Run:
```bash
python3 -m pytest -q tests/test_teacher_frontend_structure.py
cd frontend && npm run typecheck && cd ..
```
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/teacher/src/tailwind.css tests/test_teacher_frontend_structure.py
git commit -m "chore(frontend): remove dead routing css selectors"
```

## Phase P1 (Week 1): Remove Compatibility Shell

### Task 5: Replace dynamic core module loading with static import

**Files:**
- Modify: `services/api/app.py`
- Modify: `services/api/tenant_app_factory.py`
- Create: `tests/test_app_entrypoint_static_core.py`

**Step 1: Add failing tests**

```python
from pathlib import Path

def test_app_entrypoint_has_no_dynamic_module_loader() -> None:
    text = Path("services/api/app.py").read_text(encoding="utf-8")
    forbidden = ("spec_from_file_location", "exec_module(", "sys.modules.pop(")
    for item in forbidden:
        assert item not in text
```

**Step 2: Confirm failure**

Run: `python3 -m pytest -q tests/test_app_entrypoint_static_core.py`
Expected: FAIL.

**Step 3: Implement hard cut**

- 在 `app.py` 中改为静态导入 `from . import app_core as _core`。
- 删除 `_load_core()`、`_CORE_PATH`、fingerprint reload、`sys.modules` 动态替换逻辑。
- 同步清理 `tenant_app_factory.py` 的同类动态加载代码。

**Step 4: Verify**

Run:
```bash
python3 -m pytest -q tests/test_app_entrypoint_static_core.py tests/test_tenant_infra.py
python3 -m mypy --follow-imports=skip services/api/app.py services/api/tenant_app_factory.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/app.py services/api/tenant_app_factory.py tests/test_app_entrypoint_static_core.py
git commit -m "refactor(core): hard-cut dynamic module loading in app entrypoints"
```

### Task 6: Remove app_core star-export compatibility shell

**Files:**
- Modify: `services/api/app_core.py`
- Delete: `services/api/app_core_service_imports.py`
- Delete: `services/api/context_application_facade.py`
- Delete: `services/api/context_runtime_facade.py`
- Delete: `services/api/context_io_facade.py`
- Create: `services/api/core_contract.py`
- Create: `services/api/core_services.py`
- Create: `tests/test_no_compat_facades.py`

**Step 1: Add failing guard tests**

```python
from pathlib import Path

def test_compat_facades_are_removed() -> None:
    removed = [
        "services/api/context_application_facade.py",
        "services/api/context_runtime_facade.py",
        "services/api/context_io_facade.py",
        "services/api/app_core_service_imports.py",
    ]
    for path in removed:
        assert not Path(path).exists()

def test_app_core_has_no_star_imports() -> None:
    text = Path("services/api/app_core.py").read_text(encoding="utf-8")
    assert "import *" not in text
```

**Step 2: Confirm failure**

Run: `python3 -m pytest -q tests/test_no_compat_facades.py`
Expected: FAIL.

**Step 3: Implement hard cut**

- 建立显式 `core_contract.py`（Protocol 或 dataclass）列出 route/usecase 必需能力。
- 建立 `core_services.py` 聚合显式依赖，替代 `app_core` 的 re-export 机制。
- route/wiring 直接依赖 contract，不再通过 `app_core` 透传 `_impl`。
- 删除上述 compat facade 文件。
- `app_core.py` 降为最小组合根（仅常量与容器初始化），不做跨模块 re-export。

**Step 4: Verify**

Run:
```bash
python3 -m pytest -q tests/test_no_compat_facades.py tests/test_app_core_structure.py tests/test_no_star_imports_guardrail.py
python3 -m mypy --follow-imports=skip services/api
```
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api tests/test_no_compat_facades.py tests/test_app_core_structure.py tests/test_no_star_imports_guardrail.py
git commit -m "refactor(architecture): remove app_core compatibility facades and star exports"
```

### Task 7: Replace `tool_dispatch` if-chain with handler registry

**Files:**
- Modify: `services/api/tool_dispatch_service.py`
- Create: `tests/test_tool_dispatch_registry.py`

**Step 1: Add failing test**

```python
def test_tool_dispatch_uses_registry_map_not_if_chain() -> None:
    from pathlib import Path
    text = Path("services/api/tool_dispatch_service.py").read_text(encoding="utf-8")
    assert text.count('if name == "') <= 3
```

**Step 2: Confirm failure**

Run: `python3 -m pytest -q tests/test_tool_dispatch_registry.py`
Expected: FAIL.

**Step 3: Implement**

- 引入 `handlers: Dict[str, Callable]` 注册表。
- 每个工具一个 handler 函数，权限校验作为装饰或前置 wrapper。
- `tool_dispatch()` 仅做：查 registry -> validate args -> 调 handler。

**Step 4: Verify**

Run:
```bash
python3 -m pytest -q tests/test_tool_dispatch_registry.py tests/test_tool_dispatch_service_more.py
python3 -m ruff check services/api/tool_dispatch_service.py --select C901
```
Expected: PASS and no C901 for `tool_dispatch`.

**Step 5: Commit**

```bash
git add services/api/tool_dispatch_service.py tests/test_tool_dispatch_registry.py
git commit -m "refactor(dispatch): replace tool if-chain with registry handlers"
```

### Task 8: Enforce broad-exception hard policy on high-risk modules

**Files:**
- Create: `scripts/quality/check_exception_policy.py`
- Create: `tests/test_exception_policy_guard.py`
- Modify: `services/api/chart_executor.py`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/auth_registry_service.py`
- Modify: `services/api/teacher_memory_core.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Add failing policy test**

Policy:
- 禁止 `except Exception`（允许极小白名单，必须 `# policy: allowed-broad-except` 注释）。
- 禁止空 `pass`（允许同样白名单注释）。

Run: `python3 -m pytest -q tests/test_exception_policy_guard.py`
Expected: FAIL.

**Step 2: Implement minimal checker**

`check_exception_policy.py` 扫描 `services/api/*.py` 并输出违规清单。

**Step 3: Reduce violations in high-risk modules**

- 把 broad except 改为明确异常类型。
- 保留兜底时必须记录结构化日志 + 失败码。
- 删除“吞掉异常继续成功”的路径。

**Step 4: Wire into CI**

Add CI step before tests:

```bash
python scripts/quality/check_exception_policy.py
```

**Step 5: Verify and commit**

Run:
```bash
python scripts/quality/check_exception_policy.py
python3 -m pytest -q tests/test_exception_policy_guard.py tests/test_chart_executor.py tests/test_chat_job_processing_service.py
```
Expected: PASS.

```bash
git add scripts/quality/check_exception_policy.py tests/test_exception_policy_guard.py services/api/chart_executor.py services/api/chat_job_processing_service.py services/api/auth_registry_service.py services/api/teacher_memory_core.py .github/workflows/ci.yml
git commit -m "refactor(reliability): enforce strict exception policy on critical modules"
```

## Phase P2 (Week 2-3): Freeze New Clean Baseline

### Task 9: Hard-cut skill source overlay; single authoritative skills dir

**Files:**
- Modify: `services/api/skills/loader.py`
- Create: `tests/test_skill_loader_source_policy.py`

**Step 1: Add failing tests**

```python
def test_skill_loader_uses_single_source_dir_only() -> None:
    from pathlib import Path
    text = Path("services/api/skills/loader.py").read_text(encoding="utf-8")
    assert ".claude" not in text
```

**Step 2: Confirm failure**

Run: `python3 -m pytest -q tests/test_skill_loader_source_policy.py`
Expected: FAIL.

**Step 3: Implement**

- 删除 `_resolve_source_dirs` 中 `~/.claude/skills` 合并逻辑。
- 仅加载 `app_root/skills`。
- 删除 source_type=claude 相关分支。

**Step 4: Verify**

Run:
```bash
python3 -m pytest -q tests/test_skill_loader_source_policy.py tests/test_skill_routing_config.py
python3 -m mypy --follow-imports=skip services/api/skills/loader.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/skills/loader.py tests/test_skill_loader_source_policy.py
git commit -m "refactor(skills): hard-cut external overlay and keep single source"
```

### Task 10: Add complexity budget gate and burn down top offenders

**Files:**
- Create: `config/function_complexity_budget.json`
- Create: `scripts/quality/check_complexity_budget.py`
- Create: `tests/test_complexity_budget_guard.py`
- Modify: `.github/workflows/ci.yml`
- Modify top offender modules incrementally

**Step 1: Add failing gate**

初始预算建议：
- total C901 <= 40（当前 78）
- critical files (`chart_executor.py`, `tool_dispatch_service.py`, `chat_job_processing_service.py`) each <= 5

Run:
```bash
python scripts/quality/check_complexity_budget.py
python3 -m pytest -q tests/test_complexity_budget_guard.py
```
Expected: FAIL.

**Step 2: Burn down complexity in slices**

每次只拆 1-2 个函数，目标函数先做：
- `_execute_chart_exec_inner`
- `_prune_chart_envs`
- `compute_chat_reply_sync`
- `process_chat_job`

**Step 3: Verify after each slice**

Run:
```bash
python3 -m ruff check services/api --select C901
python3 -m pytest -q <touched-tests>
```

**Step 4: CI wiring + commit**

```bash
git add config/function_complexity_budget.json scripts/quality/check_complexity_budget.py tests/test_complexity_budget_guard.py .github/workflows/ci.yml services/api
git commit -m "refactor(quality): add complexity budget gate and reduce top offenders"
```

### Task 11: Repair coverage pipeline against deleted-file drift

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/test_coverage_config_integrity.py`

**Step 1: Add failing integrity test**

```python
from pathlib import Path

def test_coverage_references_existing_sources_only() -> None:
    root = Path(__file__).resolve().parent.parent
    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if "services/api/" in line and line.strip().endswith(".py\","):
            rel = line.strip().strip('",')
            assert (root / rel).exists(), rel
```

**Step 2: Confirm failure if stale entries exist**

Run: `python3 -m pytest -q tests/test_coverage_config_integrity.py`

**Step 3: Fix config and run clean coverage command**

Run:
```bash
python3 -m coverage erase
python3 -m pytest -q tests/test_coverage_config_integrity.py
python3 -m coverage report
```
Expected: no `No source for code` errors.

**Step 4: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml tests/test_coverage_config_integrity.py
git commit -m "fix(ci): align coverage config with post-deletion source tree"
```

## Final Acceptance Gates (All Must Pass)

Run in repository root:

```bash
python3 -m ruff check services/api
python3 -m mypy --follow-imports=skip services/api
python3 -m pytest -q tests/test_no_go_artifacts.py tests/test_no_compat_facades.py tests/test_exception_policy_guard.py tests/test_complexity_budget_guard.py tests/test_http_api_doc_contract.py
python3 -m pytest -q tests/test_app_core_structure.py tests/test_teacher_frontend_structure.py tests/test_student_frontend_structure.py
```

Run in `frontend/`:

```bash
npm run lint
npm run typecheck
npm run test:unit
npx playwright test --list -c playwright.teacher.config.ts
npx playwright test --list -c playwright.student.config.ts
```

Expected:
- 无已删除功能（persona/routing/go）残留路径、残留测试、残留文档。
- `except Exception` 与空 `pass` 仅白名单存在。
- C901 达到预算。
- 所有结构守卫与 CI 通过。
