# 审计剩余项修复准备清单

日期：2026-02-13  
状态：准备阶段（待进入下一轮修复）

关联文档：
- `docs/plans/2026-02-13-code-audit-findings.md`
- `docs/plans/2026-02-13-code-audit-plan.md`

## 1. 范围约束

1. `chart.exec` 默认 `trusted` 行为按当前业务要求保持不变（本轮不改）。
2. 本清单仅覆盖“findings 中仍未关闭”的问题。
3. 已完成项（IDOR、skills 角色边界、上传限额、路径穿越、rate-limit、分页上限）不重复纳入。

## 2. 剩余问题清单（按优先级）

### P0（先修）

1. Chat 锁 TTL 竞态导致重复处理（H）
- 位置：`services/api/chat_lock_service.py`、`services/api/chat_job_processing_service.py`、`services/api/workers/chat_worker_service.py`
- 现象：锁 TTL 到期会清理仍存活进程的锁，长任务可能被重复 claim。
- 目标：锁回收必须优先依赖 owner 存活性；TTL 仅作辅助，不得误删活锁。

2. Persona 头像上传内存 DoS（H）
- 位置：`services/api/routes/teacher_persona_routes.py`、`services/api/routes/student_persona_routes.py`、`services/api/teacher_persona_api_service.py`、`services/api/student_persona_api_service.py`
- 现象：路由层 `await file.read()` 先整包入内存，再校验大小。
- 目标：流式写入 + 写入过程限额；任何超限不允许全量载入内存。

### P1（次优先）

1. Persona JSON 并发与耐久性（M/L）
- 位置：`services/api/teacher_persona_api_service.py`、`services/api/student_persona_api_service.py`
- 内容：改原子写；同资源加锁；读取失败告警日志。

2. Persona 字段长度约束（M）
- 位置：`services/api/teacher_persona_api_service.py`、`services/api/student_persona_api_service.py`、相关路由/模型
- 内容：`name/summary/style_rules/few_shot_examples` 加硬上限。

3. LLM timeout 禁用风险（M）
- 位置：`llm_gateway.py`
- 内容：拒绝 `None` 超时，强制有限区间并区分 connect/read timeout。

4. 前端轮询挂死风险（M）
- 位置：`frontend/apps/shared/visibilityBackoffPolling.ts`、`frontend/apps/student/src/hooks/useChatPolling.ts`、`frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- 内容：`AbortController + timeout`，超时后恢复轮询状态机。

5. 前端 `apiBase` DOM 注入面（M）
- 位置：`frontend/apps/shared/markdown.ts`、`frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`、`frontend/apps/teacher/src/features/chat/ChatMessages.tsx`
- 内容：限制 `apiBase` schema，移除字符串拼接 HTML 属性路径。

6. 前端错误明文透传（M）
- 位置：student/teacher 多处 `res.text()` 直出链路
- 内容：统一错误映射层，仅显示白名单文案。

### P2（后续）

1. CI action SHA pin（M）
- 位置：`.github/workflows/*.yml`

2. Docker 生产基线（M/L）
- 位置：`docker-compose.yml`、`frontend/Dockerfile`
- 内容：认证默认开启、Redis 默认值与暴露策略收紧、统一非 root。

3. 上传前置客户端预校验（L）
- 位置：student/teacher 上传入口组件

4. 老 verify 契约漂移（L）
- 位置：`frontend/apps/student/src/appTypes.ts`、`frontend/apps/student/src/hooks/useVerification.ts`（legacy `/student/verify`）

## 3. 建议修复批次

### Batch A（P0）

1. 锁竞态修复（chat lock）
2. 头像上传流式限额（teacher/student persona）

验收：
- 新增并发回归：长任务处理期间不得被第二 worker 重入。
- 超大头像请求不得出现全量内存读取路径。

### Batch B（核心 P1）

1. Persona 原子写 + 并发锁 + 长度约束 + 读取告警
2. LLM timeout 强制有限
3. 轮询 timeout + abort

验收：
- 相关服务单测与类型测试通过。
- 轮询挂死复现用例可恢复。

### Batch C（前端安全与平台基线）

1. `apiBase` 注入面封堵
2. 错误映射统一
3. CI SHA pin + Docker 基线收紧

验收：
- 前端结构/类型测试通过。
- Workflow 与容器基线检查通过。

## 4. 进入修复前的验证基线

建议每批开始前先跑：

```bash
python3 -m pytest tests/test_security_auth_hardening.py tests/test_chat_job_processing_service.py tests/test_chat_lock_service.py tests/test_teacher_persona_api_service.py tests/test_student_persona_api_service.py tests/test_frontend_type_hardening.py -q
```

每批结束后按改动范围增量回归，并在 `docs/plans/2026-02-13-code-audit-findings.md` 更新“已完成/剩余”。
