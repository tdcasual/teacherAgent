# Teacher Memory Core Façade Thinning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变 teacher memory proposal-first 治理模型的前提下，把 `teacher_memory_core.py` 进一步收成兼容 façade，使 context / governance / storage / mem0 wiring 的真相回到对应 service 模块。

**Architecture:** 这一轮不重写 memory 体系，也不改外部 API。重点是把仍滞留在 `teacher_memory_core.py` 的上下文拼装辅助逻辑与 mem0 适配辅助逻辑迁回专用 service / deps builder，并让 `teacher_memory_deps.py` 优先直接组合 service 实现，而不是经由 core 私有 helper 反向拿依赖。最终 `teacher_memory_core.py` 只保留对外兼容入口、轻量 wrapper 与 deps 组装所需的极少数桥接点。

**Tech Stack:** Python 3.13、pytest、现有 `teacher_memory_*_service.py` 模块、`teacher_context_service.py`、`mem0_adapter.py`、现有 memory governance 文档。

---

> **Scope note:** `teacher_memory_auto_service.py`、`teacher_memory_governance_service.py`、`teacher_memory_storage_service.py` 已存在。本计划不是重新创建这些模块，而是完成“core 只做 façade”的最后一段收口。

### Task 1: 把 context helper 真相迁回 `teacher_context_service.py`

**Files:**
- Modify: `services/api/teacher_context_service.py`
- Modify: `services/api/teacher_memory_deps.py`
- Modify: `services/api/teacher_memory_core.py`
- Modify: `tests/test_teacher_context_service.py`
- Create: `tests/test_teacher_memory_deps.py`
- Create: `tests/test_teacher_memory_core_structure.py`

**Step 1: Write the failing test**

在 `tests/test_teacher_context_service.py` 增加两个单测，要求上下文辅助逻辑可以脱离 `teacher_memory_core.py` 单独验证：

```python
def test_teacher_session_summary_text_reads_first_summary_record() -> None:
    # session file 第一条有效记录为 session_summary 时，返回裁剪后的 summary
```

```python
def test_teacher_memory_context_text_prefers_ranked_active_records_before_markdown_fallback() -> None:
    # 有 active MEMORY records 时，输出排序后的 bullet；没有时才读 MEMORY.md
```

在 `tests/test_teacher_memory_deps.py` 新增 deps 组装回归测试：

```python
def test_teacher_context_deps_use_teacher_context_service_helpers() -> None:
    deps = _teacher_context_deps()
    assert deps.teacher_session_summary_text.__module__ == 'services.api.teacher_context_service'
    assert deps.teacher_memory_context_text.__module__ == 'services.api.teacher_context_service'
```

在 `tests/test_teacher_memory_core_structure.py` 新增 source-shape 断言：

```python
def test_teacher_memory_core_no_longer_defines_context_helpers() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'def _teacher_session_summary_text(' not in source
    assert 'def _teacher_memory_context_text(' not in source
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_context_service.py \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py
```

Expected:
- FAIL，因为 `teacher_context_service.py` 还没有承接这两个 helper；
- `teacher_memory_deps.py` 仍然通过 `tmc._teacher_session_summary_text` / `tmc._teacher_memory_context_text` 取实现；
- `teacher_memory_core.py` 仍定义这两个 helper。

**Step 3: Write minimal implementation**

- 在 `services/api/teacher_context_service.py` 中新增最小 helper 和对应 deps：

```python
@dataclass(frozen=True)
class TeacherContextTextDeps:
    teacher_session_file: Callable[[str, str], Any]
    teacher_workspace_file: Callable[[str, str], Any]
    teacher_read_text: Callable[..., str]
    teacher_memory_active_applied_records: Callable[[str, Optional[str], int], list[dict[str, Any]]]
    teacher_memory_rank_score: Callable[[dict[str, Any]], float]
    teacher_memory_context_max_entries: int
    log: Any

def teacher_session_summary_text(...): ...
def teacher_memory_context_text(...): ...
```

- 在 `services/api/teacher_memory_deps.py` 中为 `_teacher_context_deps()` 直接装配 `teacher_context_service` 的 helper，不再经由 `tmc._teacher_session_summary_text` / `tmc._teacher_memory_context_text`。
- 在 `services/api/teacher_memory_core.py` 中删除这两个 helper 定义；`teacher_build_context()` 继续保留 façade wrapper，不改其公开签名。
- 这一步避免引入新的“memory context service”文件，优先复用现有 `teacher_context_service.py`。

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_context_service.py \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_teacher_memory_core.py
```

Expected:
- PASS；
- `tests/test_teacher_memory_core.py` 继续通过，证明 façade 兼容未破坏。

**Step 5: Commit**

```bash
git add \
  services/api/teacher_context_service.py \
  services/api/teacher_memory_deps.py \
  services/api/teacher_memory_core.py \
  tests/test_teacher_context_service.py \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_teacher_memory_core.py

git commit -m "refactor(memory): move context helpers out of teacher memory core"
```

---

### Task 2: 把 mem0 与 search/apply wiring 从 core 私有 helper 反转出去

**Files:**
- Modify: `services/api/teacher_memory_deps.py`
- Modify: `services/api/teacher_memory_core.py`
- Modify: `tests/test_teacher_memory_deps.py`
- Modify: `tests/test_teacher_memory_core_structure.py`
- Test: `tests/test_teacher_memory_core.py`
- Test: `tests/test_teacher_memory_storage_service.py`

**Step 1: Write the failing test**

在 `tests/test_teacher_memory_deps.py` 增加 deps 直连断言：

```python
def test_teacher_memory_search_deps_use_mem0_adapter_directly() -> None:
    deps = _teacher_memory_search_deps()
    assert deps.mem0_search.__module__ == 'services.api.mem0_adapter'
```

```python
def test_teacher_memory_apply_deps_use_mem0_adapter_directly() -> None:
    deps = _teacher_memory_apply_deps()
    assert deps.mem0_should_index_target.__module__ == 'services.api.mem0_adapter'
    assert deps.mem0_index_entry.__module__ == 'services.api.mem0_adapter'
```

在 `tests/test_teacher_memory_core_structure.py` 追加：

```python
def test_teacher_memory_core_no_longer_defines_mem0_bridge_helpers() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'def _teacher_mem0_search(' not in source
    assert 'def _teacher_mem0_should_index_target(' not in source
    assert 'def _teacher_mem0_index_entry(' not in source
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py
```

Expected:
- FAIL，因为 `_teacher_memory_search_deps()` 和 `_teacher_memory_apply_deps()` 仍通过 `tmc._teacher_mem0_*` 取实现；
- `teacher_memory_core.py` 仍定义 mem0 bridge helper。

**Step 3: Write minimal implementation**

- 在 `services/api/teacher_memory_deps.py` 中：
  - `mem0_search` 直接绑定 `services.api.mem0_adapter.teacher_mem0_search`
  - `mem0_should_index_target` 直接绑定 `services.api.mem0_adapter.teacher_mem0_should_index_target`
  - `mem0_index_entry` 直接绑定 `services.api.mem0_adapter.teacher_mem0_index_entry`
- 删除 `services/api/teacher_memory_core.py` 里的 `_teacher_mem0_search()`、`_teacher_mem0_should_index_target()`、`_teacher_mem0_index_entry()`。
- 保持 search / apply / storage service 行为不变，不改 mem0 adapter 的容错语义。

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_teacher_memory_core.py \
  tests/test_teacher_memory_storage_service.py
```

Expected:
- PASS；
- 兼容 façade 仍能跑通 proposal/search/apply 相关路径。

**Step 5: Commit**

```bash
git add \
  services/api/teacher_memory_deps.py \
  services/api/teacher_memory_core.py \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_teacher_memory_core.py \
  tests/test_teacher_memory_storage_service.py

git commit -m "refactor(memory): remove mem0 bridge indirection from core"
```

---

### Task 3: 让 `teacher_memory_deps.py` 优先直接组合 service 真相，收紧 core 为兼容层

**Files:**
- Modify: `services/api/teacher_memory_deps.py`
- Modify: `services/api/teacher_memory_core.py`
- Modify: `tests/test_teacher_memory_deps.py`
- Modify: `tests/test_teacher_memory_core_structure.py`
- Modify: `docs/reference/memory-governance.md`
- Test: `tests/test_teacher_memory_auto_service.py`
- Test: `tests/test_teacher_memory_governance_service.py`
- Test: `tests/test_teacher_memory_record_service.py`
- Test: `tests/test_teacher_memory_storage_service.py`
- Test: `tests/test_teacher_memory_insights.py`

**Step 1: Write the failing test**

在 `tests/test_teacher_memory_deps.py` 增加对 service-first 组装的最小回归：

```python
def test_teacher_memory_deps_stop_using_core_private_governance_helpers() -> None:
    source = Path('services/api/teacher_memory_deps.py').read_text(encoding='utf-8')
    assert 'tmc._teacher_memory_find_duplicate' not in source
    assert 'tmc._teacher_memory_auto_quota_reached' not in source
    assert 'tmc._teacher_memory_find_conflicting_applied' not in source
    assert 'tmc._teacher_memory_mark_superseded' not in source
```

并在 `tests/test_teacher_memory_core_structure.py` 中增加约束：

```python
def test_teacher_memory_core_keeps_public_facade_entries_only() -> None:
    source = Path('services/api/teacher_memory_core.py').read_text(encoding='utf-8')
    assert 'teacher_memory_propose(' in source
    assert 'teacher_memory_apply(' in source
    assert 'teacher_build_context(' in source
```

这里不要求“一次性去掉 core 里所有私有 wrapper”，但要求 deps builder 不再继续以 core 私有 helper 作为默认真相源。

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py
```

Expected:
- FAIL，因为 `teacher_memory_deps.py` 现在仍大量通过 `tmc._teacher_memory_*` 取规则/治理/记录函数。

**Step 3: Write minimal implementation**

- 在 `services/api/teacher_memory_deps.py` 中，优先直接组合现有 service 模块的公开实现：
  - rule helpers 来自 `teacher_memory_rules_service.py`
  - governance helpers 来自 `teacher_memory_governance_service.py`
  - record helpers 来自 `teacher_memory_record_service.py`
  - storage helpers 来自 `teacher_memory_storage_service.py`
  - store / event helpers 来自 `teacher_memory_store_service.py`
- 仅在外部兼容 API 仍必须保留时，才让 `teacher_memory_core.py` 继续提供 public façade wrapper。
- 保留 `_app_core()` 这种为兼容 wiring 所必需的少量桥接，不做大范围删除。
- 删除 refactor 后明显不再使用的 `json` / `re` / `Path.open` / mem0 helper 等残余实现和导入。

**Step 4: Run test to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_teacher_memory_auto_service.py \
  tests/test_teacher_memory_governance_service.py \
  tests/test_teacher_memory_record_service.py \
  tests/test_teacher_memory_storage_service.py \
  tests/test_teacher_memory_insights.py \
  tests/test_teacher_memory_core.py
```

Expected:
- PASS；
- deps builder 的真相优先来自专用 service，而不是 core 私有 helper；
- `teacher_memory_core.py` 继续只是兼容入口层。

**Step 5: Update docs**

在 `docs/reference/memory-governance.md` 补一句：
- `teacher_memory_deps.py` 优先直接装配 `teacher_memory_*_service.py` 与 `teacher_context_service.py` 的实现；`teacher_memory_core.py` 仅保留兼容 façade。

**Step 6: Commit**

```bash
git add \
  services/api/teacher_memory_deps.py \
  services/api/teacher_memory_core.py \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  docs/reference/memory-governance.md

git commit -m "refactor(memory): make teacher memory deps service-first"
```

---

### Task 4: Final regression and façade cleanup verification

**Files:**
- Reference: `services/api/teacher_memory_core.py`
- Reference: `services/api/teacher_memory_deps.py`
- Reference: `services/api/teacher_context_service.py`
- Reference: `docs/reference/memory-governance.md`

**Step 1: Run focused memory regression**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_context_service.py \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_teacher_memory_core.py \
  tests/test_teacher_memory_auto_service.py \
  tests/test_teacher_memory_governance_service.py \
  tests/test_teacher_memory_record_service.py \
  tests/test_teacher_memory_storage_service.py \
  tests/test_teacher_memory_insights.py \
  tests/test_teacher_session_compaction_service.py
```

Expected: PASS。

**Step 2: Run broader guardrails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_backend_complexity_targets.py \
  tests/test_app_core_decomposition.py \
  tests/test_no_star_imports_guardrail.py
```

Expected: PASS。

**Step 3: Run diff guard**

Run:

```bash
git diff --check
```

Expected: PASS。

**Step 4: Commit**

```bash
git add services/api/teacher_context_service.py services/api/teacher_memory_deps.py services/api/teacher_memory_core.py docs/reference/memory-governance.md tests/test_teacher_context_service.py tests/test_teacher_memory_deps.py tests/test_teacher_memory_core_structure.py tests/test_teacher_memory_core.py tests/test_teacher_memory_auto_service.py tests/test_teacher_memory_governance_service.py tests/test_teacher_memory_record_service.py tests/test_teacher_memory_storage_service.py tests/test_teacher_memory_insights.py tests/test_teacher_session_compaction_service.py

git commit -m "refactor(memory): thin teacher memory core facade"
```
