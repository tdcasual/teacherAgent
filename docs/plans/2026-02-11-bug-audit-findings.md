# Bug 审计报告与修复设计

日期: 2026-02-11
范围: services/api 全模块静态分析
状态: 部分修复（P0+P1+M3 已完成，P2/P3 待推进）

## 概述

对项目后端代码进行系统性 bug 审计，覆盖模块代理、多租户隔离、技能系统、
聊天锁、Agent 运行时、文件原子操作等核心模块。共发现 14 个问题，
按严重程度分为高危(3)、中危(5)、低危(6)。

---

## 高危问题

### H1: skill_id="." 可删除整个 teacher_skills 目录

**位置:** `teacher_skill_service.py:54-59, 140-144`

**问题:** `_ensure_safe_path` 检查条件为:
```python
if resolved_base not in resolved_target.parents and resolved_target != resolved_base:
    raise ValueError("path traversal detected")
```
当 `skill_id="."` 时，`teacher_skills_dir / "."` resolve 后等于 `teacher_skills_dir` 本身，
通过检查后 `shutil.rmtree(skill_dir)` 删除整个目录。

**修复方案:**
1. 在所有 CRUD 入口加 `_SKILL_ID_RE` 格式校验（复用 `skill_auto_router.py:13` 的正则）
2. 修改 `_ensure_safe_path` 为 `resolved_target not in (resolved_base, *resolved_base.parents)`

```python
# 修复代码
import re
_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")

def _validate_skill_id(skill_id: str) -> None:
    if not _SKILL_ID_RE.match(skill_id):
        raise ValueError(f"invalid skill_id: {skill_id!r}")

def _ensure_safe_path(base: Path, target: Path) -> None:
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    if resolved_target == resolved_base or resolved_base not in resolved_target.parents:
        raise ValueError("path traversal detected")
```

**影响范围:** `create_teacher_skill`, `update_teacher_skill`, `delete_teacher_skill`, `import_skill_from_github`
**工作量:** 小（约 20 行改动）

---

### H2: 多租户数据泄漏 — get_app_core() 静默回退

**位置:** `wiring/__init__.py:11-17`, `teacher_memory_deps.py:86-88`, `teacher_memory_core.py:195-198`

**问题:**
- `get_app_core()` 在 `CURRENT_CORE` 未设置时回退到默认租户模块，无日志无告警
- `teacher_memory_deps.py` 和 `teacher_memory_core.py` 完全绕过 `CURRENT_CORE`，直接 import `app_core`
- 后台任务、worker 线程中所有操作静默执行在默认租户数据上

**修复方案:**
1. `get_app_core()` 回退路径加 `warnings.warn()` 或 `logger.warning()`
2. `teacher_memory_deps.py` 和 `teacher_memory_core.py` 的 `_app_core()` 改为调用 `get_app_core()`
3. 长期: 考虑在非请求上下文中让 `get_app_core()` 抛异常而非静默回退

```python
# wiring/__init__.py 修复
def get_app_core():
    _ctx = CURRENT_CORE.get(None)
    if _ctx is not None:
        return _ctx
    import logging
    logging.getLogger(__name__).warning("CURRENT_CORE not set, falling back to default tenant")
    from services.api import app_core as _mod
    return _mod
```

**影响范围:** 所有通过 `_app_core()` 访问核心模块的代码路径
**工作量:** 中（需逐一排查所有 `from services.api import app_core` 的直接导入）

---

### H3: 文件锁 TOCTOU 竞态 — 两个进程可同时获取排他锁

**位置:** `chat_lock_service.py:56-68`, `job_repository.py:123-160`

**问题:** 锁获取流程为 `os.open(O_CREAT|O_EXCL)` → 失败时检查 PID/TTL → `unlink` → 重试。
在 `unlink` 和下一次 `os.open` 之间，另一个进程可以创建同名锁文件，导致两个进程都认为自己持有锁。
多 worker uvicorn 部署下可导致同一 chat job 被重复处理。

两套几乎相同的实现（`chat_lock_service.py` 和 `job_repository.py`）都存在此问题。

**修复方案:**
1. 改用 `fcntl.flock()` 实现进程级排他锁（POSIX 系统）
2. 合并两套锁实现为一个，消除代码重复
3. 短期替代: 在 `unlink` 后立即用 `os.open(O_CREAT|O_EXCL)` 而非 `continue` 重试

```python
# 推荐: 基于 fcntl 的锁实现
import fcntl

def try_acquire_lockfile(path: Path, ttl_sec: int = 300) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        return True
    except OSError:
        os.close(fd)
        return False
```

**影响范围:** `chat_job_processing_service.py`, `app_core.py:450`
**工作量:** 中（需替换两处实现 + 更新所有调用点）

---

## 中危问题

### M1: agent_service.py JSON fallback 路径异常未捕获

**位置:** `agent_service.py:381-382`

**问题:** JSON-in-content 工具调用路径中 `deps.tool_dispatch(name, args_dict, role_hint)` 无 try/except，
异常直接崩溃整个 agent runtime。

**修复:** 包裹 try/except，返回错误信息作为 tool result 继续对话循环。
**工作量:** 小

### M2: fs_atomic.py 缺少 fsync

**位置:** `fs_atomic.py:16-23`

**问题:** `atomic_write_json` 在 `write_text` 后未调用 `os.fsync()`，断电/崩溃时可能丢失数据。

**修复:** 在 `tmp.replace(path)` 前加 `os.fsync(fd)` 和目录 fsync。
**工作量:** 小（约 5 行）

### M3: skills/loader.py 缓存失效竞态

**位置:** `loader.py:252-300`

**问题:** 释放 `_CACHE_LOCK` 后构建 `LoadedSkills`，再重新获取锁写入。
窗口期内 `clear_cache()` 的效果会被过期数据覆盖。

**修复:** 在持有锁的情况下完成整个 load + write 操作，或使用 double-check 模式。
**工作量:** 小

### M4: content_catalog_service.py 静默吞掉 CSV 解析错误

**位置:** `content_catalog_service.py:68-69, 86-87`

**问题:** `except Exception: return {}` 无日志，无法区分"无数据"和"数据损坏"。

**修复:** 加 `logger.exception()` 日志。
**工作量:** 极小

### M5: app.py __setattr__ 静默吞掉异常

**位置:** `app.py:107-115`

**问题:** `except Exception: pass` 让 monkey-patch 失败无感知，影响测试可靠性。

**修复:** 至少加 `logger.debug()` 或在测试环境下 re-raise。
**工作量:** 极小

---

## 低危问题

### L1: subject_score_guard_service.py 混合脚本 token 匹配

**位置:** `subject_score_guard_service.py:40-47`

**问题:** CJK 分支用原始 `text` 搜索但 `token_norm` 已 lower()，混合中英文 token 大小写不匹配。
**当前状态:** 同义词表均为纯中文或纯英文，暂不触发。
**修复:** CJK 分支也用 `lowered` 搜索。

### L2: subject_score_guard_service.py guard 函数中做文件 I/O

**位置:** `subject_score_guard_service.py:103-117`

**问题:** 根据用户数据中的 manifest 路径遍历目录，可能延迟抖动 + 轻微路径探测风险。
**修复:** 将文件名信息预存到 overview dict 中，guard 函数只做纯数据检查。

### L3: api_models.py 请求模型缺少长度限制

**位置:** `api_models.py:140-157`

**问题:** `title`, `description`, `keywords` 等字段无 `max_length`，可用于资源耗尽。
**修复:** 加 `Field(max_length=...)` 和 `conlist(max_length=...)`。

### L4: teacher_skill_service.py urlopen 跟随重定向

**位置:** `teacher_skill_service.py:186`

**问题:** `urllib.request.urlopen` 默认跟随重定向，可能绕过 SSRF 主机名检查。
**修复:** 使用自定义 opener 禁用重定向，或验证最终响应 URL 的主机名。

### L5: app.py 部分初始化模块暴露

**位置:** `app.py:35-38`

**问题:** 模块注册到 `sys.modules` 后才执行 `exec_module`，模块级调用 `get_app_core()` 会拿到不完整模块。
**当前状态:** 靠约定安全，无防护。
**修复:** 在 wiring 包文档中明确标注此约束。

### L6: GitHub import 静默覆盖已有技能

**位置:** `teacher_skill_service.py:229-231`

**问题:** `import_skill_from_github` 不检查已有技能，直接覆盖。与 `create` 行为不一致。
**修复:** 加 `overwrite: bool = False` 参数，默认拒绝覆盖。

---

## 修复优先级路线图

| 阶段 | 问题 | 预计改动量 |
|------|------|-----------|
| P0 (立即) | H1 skill_id 校验 | ~20 行 |
| P0 (立即) | M1 agent 异常捕获 | ~10 行 |
| P1 (本周) | M2 fsync | ~5 行 |
| P1 (本周) | M4+M5 日志补全 | ~10 行 |
| P1 (本周) | L3 请求长度限制 | ~15 行 |
| P2 (下周) | H3 锁实现重构 | ~80 行 |
| P2 (下周) | M3 缓存竞态 | ~20 行 |
| P3 (择机) | H2 多租户隔离加固 | ~50 行 + 排查 |
| P3 (择机) | L1-L6 其余低危 | 各 5-20 行 |
