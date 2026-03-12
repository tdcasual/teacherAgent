# Teacher Memory Final Façade Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变 teacher memory proposal-first 治理模型、外部 API 和持久化格式的前提下，切断 `teacher_memory_deps.py` 对 `teacher_memory_core.py` 的回拉依赖，并把 `teacher_memory_core.py` 收成显式导出、可验证的兼容 façade。

**Architecture:** 这一轮不新增 memory 子系统，也不重写现有 `teacher_memory_*_service.py`。重点是把剩余的 compaction / workspace / context wiring 真相继续压回对应 helper / service / deps builder，让 `teacher_memory_deps.py` 不再通过 `tmc` 间接取实现；随后删除 `teacher_memory_core.py` 中只为旧 wiring 存在的内部 wrapper，改成显式 import + 显式 `__all__` 的 façade。最终结果应是：`teacher_memory_deps.py` 成为默认依赖真相层，`teacher_memory_core.py` 只保留少量公开兼容入口。

**Tech Stack:** Python 3.13、pytest、现有 `teacher_memory_*_service.py` 模块、`teacher_session_compaction_helpers.py`、`teacher_session_compaction_service.py`、`teacher_workspace_service.py`、ruff guard tests。

---

> **Scope note:** 本计划不改 proposal/apply/search 的对外行为，不迁移数据目录结构，不删除 `teacher_memory_core.py` 模块本身。目标是“收紧 façade 边界”，不是“推翻 memory 体系”。

### Task 1: 把 compaction wiring 真相从 core 回拉中移除

**Files:**
- Modify: `services/api/teacher_memory_deps.py`
- Modify: `tests/test_teacher_memory_deps.py`
- Test: `tests/test_teacher_memory_auto_service.py`
- Test: `tests/test_teacher_session_compaction_service.py`
- Test: `tests/test_teacher_memory_core.py`

**Step 1: Write the failing test**

在 `tests/test_teacher_memory_deps.py` 增加 direct-wiring 回归测试：

```python
from services.api.teacher_memory_deps import (
    _teacher_memory_auto_deps,
    _teacher_session_compaction_deps,
)


def test_teacher_memory_auto_deps_use_compaction_helpers_directly() -> None:
    deps = _teacher_memory_auto_deps()
    assert deps.compact_transcript.__module__ == "services.api.teacher_session_compaction_helpers"


def test_teacher_session_compaction_deps_use_compaction_helpers_directly() -> None:
    deps = _teacher_session_compaction_deps()
    assert deps.teacher_compact_allowed.__module__ == "services.api.teacher_session_compaction_helpers"
    assert deps.teacher_compact_summary.__module__ == "services.api.teacher_session_compaction_helpers"
    assert deps.write_teacher_session_records.__module__ == "services.api.teacher_session_compaction_helpers"
    assert deps.mark_teacher_session_compacted.__module__ == "services.api.teacher_session_compaction_helpers"
```

再加 source-shape 断言，防止继续从 core 回拉：

```python
def test_teacher_memory_deps_stop_using_core_compaction_helpers() -> None:
    source = Path("services/api/teacher_memory_deps.py").read_text(encoding="utf-8")
    assert "tmc._teacher_compact_transcript" not in source
    assert "tmc._teacher_compact_allowed" not in source
    assert "tmc._teacher_compact_summary" not in source
    assert "tmc._mark_teacher_session_compacted" not in source
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py
```

Expected:
- FAIL，因为 `_teacher_memory_auto_deps()` 仍然把 `compact_transcript` 指到 `tmc._teacher_compact_transcript`
- FAIL，因为 `_teacher_session_compaction_deps()` 仍然通过 `tmc._teacher_compact_*` / `tmc._mark_teacher_session_compacted` 取实现

**Step 3: Write minimal implementation**

- 在 `services/api/teacher_memory_deps.py` 中直接导入：

```python
from .teacher_session_compaction_helpers import (
    _mark_teacher_session_compacted,
    _teacher_compact_allowed,
    _teacher_compact_summary,
    _teacher_compact_transcript,
    write_teacher_session_records,
)
```

- 把 `_teacher_memory_auto_deps()` 中的：
  - `compact_transcript=tmc._teacher_compact_transcript`
  改为：
  - `compact_transcript=_teacher_compact_transcript`

- 把 `_teacher_session_compaction_deps()` 中的：
  - `teacher_compact_allowed=tmc._teacher_compact_allowed`
  - `teacher_compact_summary=tmc._teacher_compact_summary`
  - `write_teacher_session_records=tmc.write_teacher_session_records`
  - `mark_teacher_session_compacted=tmc._mark_teacher_session_compacted`
  改为 helper 模块直连绑定。

- 这一 task 不修改 compaction 行为本身，只去掉“helper 真相绕 core 一圈”的间接层。

**Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_memory_auto_service.py \
  tests/test_teacher_session_compaction_service.py \
  tests/test_teacher_memory_core.py
```

Expected:
- PASS
- 现有 session compaction 与 auto-flush 行为不变

**Step 5: Commit**

```bash
git add \
  services/api/teacher_memory_deps.py \
  tests/test_teacher_memory_deps.py

git commit -m "refactor(memory): wire compaction helpers directly in deps"
```

---

### Task 2: 切断 `teacher_memory_deps.py` 对 `teacher_memory_core.py` 的 bridge 依赖

**Files:**
- Modify: `services/api/teacher_memory_deps.py`
- Modify: `tests/test_teacher_memory_deps.py`
- Test: `tests/test_teacher_context_service.py`
- Test: `tests/test_teacher_memory_search_service.py`
- Test: `tests/test_teacher_memory_insights.py`
- Test: `tests/test_teacher_memory_auto_service.py`

**Step 1: Write the failing test**

在 `tests/test_teacher_memory_deps.py` 中新增结构断言：

```python
def test_teacher_memory_deps_no_longer_imports_teacher_memory_core() -> None:
    source = Path("services/api/teacher_memory_deps.py").read_text(encoding="utf-8")
    assert "from . import teacher_memory_core as _mod" not in source
    assert "def _tmc()" not in source
    assert "tmc." not in source
```

再加一条约束，确保 workspace/context 默认 wiring 也不经由 core 公共函数回拉：

```python
def test_teacher_memory_deps_stop_using_core_workspace_helpers() -> None:
    source = Path("services/api/teacher_memory_deps.py").read_text(encoding="utf-8")
    assert "tmc.ensure_teacher_workspace" not in source
    assert "tmc.teacher_read_text" not in source
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py
```

Expected:
- FAIL，因为 `teacher_memory_deps.py` 仍定义 `_tmc()` 并从 `teacher_memory_core` 懒加载
- FAIL，因为多个 deps builder 还在使用 `tmc.ensure_teacher_workspace` / `tmc.teacher_read_text`

**Step 3: Write minimal implementation**

- 在 `services/api/teacher_memory_deps.py` 中直接导入：

```python
from .teacher_workspace_service import (
    TeacherWorkspaceDeps,
    ensure_teacher_workspace as ensure_teacher_workspace_impl,
    teacher_read_text as teacher_read_text_impl,
)
```

- 新增本地 bridge helper，直接走 service + deps，而不是走 core：

```python
def _ensure_teacher_workspace(teacher_id: str):
    return ensure_teacher_workspace_impl(teacher_id, deps=_teacher_workspace_deps())
```

- 将所有 `ensure_teacher_workspace=tmc.ensure_teacher_workspace` 替换为 `_ensure_teacher_workspace`
- 将所有 `teacher_read_text=tmc.teacher_read_text` 替换为 `teacher_read_text_impl`
- 更新 `_teacher_context_deps()` 里的 `teacher_read_text` 绑定和 reader builder 绑定
- 删除 `_tmc()` 及其唯一 import path

**Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_deps.py \
  tests/test_teacher_context_service.py \
  tests/test_teacher_memory_search_service.py \
  tests/test_teacher_memory_insights.py \
  tests/test_teacher_memory_auto_service.py \
  tests/test_teacher_memory_core.py
```

Expected:
- PASS
- `teacher_memory_deps.py` 不再需要 import `teacher_memory_core.py`
- context/search/insights/auto 仍使用相同业务规则，但默认真相源回到对应 service/helper

**Step 5: Commit**

```bash
git add \
  services/api/teacher_memory_deps.py \
  tests/test_teacher_memory_deps.py

git commit -m "refactor(memory): remove deps bridge back to teacher memory core"
```

---

### Task 3: 把 `teacher_memory_core.py` 收成显式 façade，并删掉 star-import 债务

**Files:**
- Modify: `services/api/teacher_memory_core.py`
- Modify: `tests/test_teacher_memory_core_structure.py`
- Modify: `tests/test_no_star_imports_guardrail.py`
- Modify: `tests/test_ruff_facade_allowlist.py`
- Modify: `pyproject.toml`
- Modify: `docs/reference/memory-governance.md`
- Test: `tests/test_teacher_memory_core.py`
- Test: `tests/test_app_core_decomposition.py`
- Test: `tests/test_backend_complexity_targets.py`

**Step 1: Write the failing test**

在 `tests/test_teacher_memory_core_structure.py` 增加 façade 边界测试：

```python
def test_teacher_memory_core_uses_no_star_imports() -> None:
    source = Path("services/api/teacher_memory_core.py").read_text(encoding="utf-8")
    assert "import *" not in source


def test_teacher_memory_core_declares_explicit_public_exports() -> None:
    source = Path("services/api/teacher_memory_core.py").read_text(encoding="utf-8")
    assert "__all__ = [" in source
    assert '"teacher_memory_propose"' in source or "'teacher_memory_propose'" in source
    assert '"teacher_memory_apply"' in source or "'teacher_memory_apply'" in source
    assert '"teacher_build_context"' in source or "'teacher_build_context'" in source
```

增加 dead-wrapper 结构断言，限制这一轮已经失去用途的内部 helper 继续留在 core：

```python
def test_teacher_memory_core_no_longer_keeps_internal_rule_store_wrappers() -> None:
    source = Path("services/api/teacher_memory_core.py").read_text(encoding="utf-8")
    assert "def _teacher_memory_parse_dt(" not in source
    assert "def _teacher_memory_record_ttl_days(" not in source
    assert "def _teacher_memory_rank_score(" not in source
    assert "def _teacher_memory_load_record(" not in source
    assert "def _teacher_memory_recent_proposals(" not in source
    assert "def _teacher_session_compaction_cycle_no(" not in source
```

在 `tests/test_no_star_imports_guardrail.py` 中把 allowlist 收紧为只允许 `app_core.py`：

```python
ALLOWED = {
    "services/api/app_core.py",
}
```

在 `tests/test_ruff_facade_allowlist.py` 中把断言改为：

```python
assert '"services/api/teacher_memory_core.py"' not in text
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_core_structure.py \
  tests/test_no_star_imports_guardrail.py \
  tests/test_ruff_facade_allowlist.py
```

Expected:
- FAIL，因为 `teacher_memory_core.py` 仍有 `import *`
- FAIL，因为 `pyproject.toml` 和 no-star allowlist 仍把 `teacher_memory_core.py` 当特殊 façade 文件
- FAIL，因为上述 internal-only wrapper 仍存在于 core

**Step 3: Write minimal implementation**

- 在 `services/api/teacher_memory_core.py` 中删除：
  - `from .teacher_session_compaction_helpers import *`
  - `from .teacher_memory_deps import *`

- 保留现有 explicit import 列表，并新增显式 `__all__`，只导出公开 façade 入口，例如：

```python
__all__ = [
    "ensure_teacher_workspace",
    "teacher_read_text",
    "maybe_compact_teacher_session",
    "teacher_build_context",
    "teacher_memory_search",
    "teacher_memory_list_proposals",
    "teacher_memory_insights",
    "teacher_memory_propose",
    "teacher_memory_apply",
    "teacher_memory_delete_proposal",
    "teacher_memory_auto_propose_from_turn",
    "teacher_memory_auto_flush_from_session",
]
```

- 删除已经只为旧 `deps -> core` 回拉存在的 internal-only thin wrapper：
  - `_teacher_memory_parse_dt`
  - `_teacher_memory_record_ttl_days`
  - `_teacher_memory_rank_score`
  - `_teacher_memory_load_record`
  - `_teacher_memory_recent_proposals`
  - `_teacher_session_compaction_cycle_no`
  - 以及它们牵连的其它纯内部 dead wrapper；删除前先用 `rg` 确认仓库内无真实调用方

- 如果删除过程中发现确有外部调用方：
  - 只恢复那一个兼容 shim
  - 在 `teacher_memory_core.py` 里加一行简短注释说明“兼容保留原因”
  - 不允许为了一个 shim 恢复 `import *`

- 在 `pyproject.toml` 里移除 `teacher_memory_core.py` 的 per-file ignore
- 更新 `docs/reference/memory-governance.md`，明确：
  - `teacher_memory_deps.py` 不再从 core 获取默认 wiring 真相
  - `teacher_memory_core.py` 是显式兼容 façade，而不是隐式 helper 聚合层

**Step 4: Run tests to verify it passes**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_teacher_memory_core_structure.py \
  tests/test_no_star_imports_guardrail.py \
  tests/test_ruff_facade_allowlist.py \
  tests/test_teacher_memory_core.py \
  tests/test_app_core_decomposition.py \
  tests/test_backend_complexity_targets.py \
  tests/test_teacher_memory_deps.py
```

Run:

```bash
./.venv/bin/python -m ruff check services/api/teacher_memory_core.py services/api/teacher_memory_deps.py
```

Expected:
- PASS
- `teacher_memory_core.py` 不再依赖 star import 才能工作
- `app_core` 继续能从 core 绑定公开 delegate export
- memory façade 边界变成显式、可测试、可维护

**Step 5: Commit**

```bash
git add \
  services/api/teacher_memory_core.py \
  tests/test_teacher_memory_core_structure.py \
  tests/test_no_star_imports_guardrail.py \
  tests/test_ruff_facade_allowlist.py \
  pyproject.toml \
  docs/reference/memory-governance.md

git commit -m "refactor(memory): finalize teacher memory facade boundaries"
```

---

## Recommended Execution Order

1. **Task 1** — 先切掉 compaction wiring 的 core 回拉，风险最低，收益最直接。
2. **Task 2** — 再切断 `teacher_memory_deps.py -> teacher_memory_core.py` 的整体 bridge，让 deps 真正独立。
3. **Task 3** — 最后收 `teacher_memory_core.py` 的 star-import / export / dead-wrapper 债务。

## Exit Criteria

- `services/api/teacher_memory_deps.py` 中不再存在 `_tmc()`、`tmc.` 或对 `teacher_memory_core.py` 的默认 wiring 回拉。
- compaction / workspace / context 默认真相直接来自对应 helper / service / deps builder。
- `services/api/teacher_memory_core.py` 不再使用 `import *`。
- `teacher_memory_core.py` 只显式导出公开 façade 入口，不再作为隐式 helper 聚合层。
- 相关 guard tests 能阻止未来再把 wiring 真相塞回 core。

## Non-Goals

- 不删除 `teacher_memory_core.py` 模块本身。
- 不改 teacher memory proposal/apply/search 的外部契约。
- 不引入新的 memory provider、消息总线或持久化后端。
- 不在这一轮扩展 student memory 模型或重做治理规则。
