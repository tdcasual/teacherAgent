# 后端 API 服务崩溃修复方案

## 问题诊断

### 主要崩溃原因（已验证）

服务启动时的崩溃链：

```
app_lifespan → bootstrap.start_runtime()
  → start_tenant_runtime()
    → get_app_queue_backend()
      → get_queue_backend()
        → RuntimeError("RQ backend required")  ← 没有配置 JOB_QUEUE_BACKEND
```

即使配置了 RQ：
```
queue_runtime.start_runtime()
  → require_redis()
    → RuntimeError("Redis required: REDIS_URL not set")  ← Redis 未运行
```

**根本原因**：`queue_backend.py` 只支持 RQ 后端，没有本地开发模式的回退方案。
`.env` 文件缺少 `JOB_QUEUE_BACKEND=rq` 和 `REDIS_URL` 配置。

### 次要问题（代码审计发现）

| # | 严重度 | 文件 | 问题 |
|---|--------|------|------|
| 1 | CRITICAL | queue_backend.py:35 | `get_queue_backend()` 无 inline 回退 |
| 2 | CRITICAL | lifecycle.py:10 | `start_runtime()` 无异常处理 |
| 3 | HIGH | auth_service.py:26 | `AuthPrincipal.claims=None` 可导致 AttributeError |
| 4 | HIGH | app.py:86 | 中间件只捕获 AuthError，其他异常变 500 |
| 5 | MEDIUM | 多个路由文件 | async def 中直接调用同步 I/O，阻塞事件循环 |
| 6 | MEDIUM | chat_start_service.py:182 | 返回 `ok:True` + `status:"failed"` 误导前端 |
| 7 | MEDIUM | 30+ 处 | `except Exception: pass` 静默吞掉错误 |

---

## 修复方案

### Phase 1: 启动崩溃修复（优先级最高）

#### 1.1 添加 inline 队列后端回退

**文件**: `services/api/queue/queue_backend.py`

```python
def get_queue_backend(*, tenant_id=None):
    if rq_enabled():
        return RqQueueBackend(tenant_id=tenant_id)
    # 回退到 inline 后端（开发模式）
    return _get_inline_fallback_backend()
```

新增 `InlineQueueBackend` 类，实现 `QueueBackend` 协议，
使用内存队列 + 线程池处理任务（与 pytest 模式的 inline backend 类似）。

#### 1.2 lifecycle 添加异常处理

**文件**: `services/api/runtime/lifecycle.py`

```python
@asynccontextmanager
async def app_lifespan(_app):
    try:
        bootstrap.start_runtime()
    except Exception:
        _log.error("Runtime startup failed; running in degraded mode", exc_info=True)
    try:
        yield
    finally:
        try:
            bootstrap.stop_runtime()
        except Exception:
            _log.error("Runtime shutdown error", exc_info=True)
```

#### 1.3 require_redis 改为可选

**文件**: `services/api/runtime/queue_runtime.py`

当使用 inline 后端时，跳过 `require_redis()` 调用。
通过检查 backend 类型决定是否需要 Redis。

### Phase 2: 认证与中间件修复

#### 2.1 AuthPrincipal.claims 默认值

**文件**: `services/api/auth_service.py`

```python
claims: Dict[str, Any] = field(default_factory=dict)
```

#### 2.2 中间件异常处理

**文件**: `services/api/app.py`

在 `_set_core_context` 中间件添加通用异常捕获：

```python
except AuthError as exc:
    return JSONResponse(status_code=exc.status_code, ...)
except Exception:
    _log.exception("Unhandled error in auth middleware")
    return JSONResponse(status_code=500, content={"detail": "internal_error"})
```

### Phase 3: 事件循环阻塞修复

将路由处理函数从 `async def` 改为 `def`（FastAPI 会自动在线程池中运行同步函数），
或者在 async 函数中使用 `run_in_threadpool()` 包装同步调用。

**涉及文件**:
- `routes/exam_routes.py`
- `routes/teacher_routes.py`
- `routes/student_routes.py`

### Phase 4: 静默异常修复

对关键路径的 `except Exception: pass` 添加日志记录：

```python
except Exception:
    _log.warning("xxx failed", exc_info=True)
```

优先修复：
- `chat_status_service.py` — 重新入队失败
- `chat_job_repository.py` — 文件读写失败
- `chat_idempotency_service.py` — 幂等性索引写入失败
- `assignment_upload_draft_service.py` — 草稿保存失败

---

## 实施顺序

1. **Phase 1** (启动崩溃) — 立即修复，解决服务无法启动的问题
2. **Phase 2** (认证) — 紧随其后，防止运行时 500 错误
3. **Phase 3** (事件循环) — 性能优化，防止高并发下的请求超时
4. **Phase 4** (静默异常) — 提高可观测性，便于后续排查问题
