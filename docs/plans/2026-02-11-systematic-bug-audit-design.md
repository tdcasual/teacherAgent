# 系统性 Bug 审计规划方案

日期: 2026-02-11
状态: Phase 1+2 完成，Phase 3 待执行

## 背景

前一轮审计发现并修复了 7 个 bug（H1-H3, M1-M5），新增 25 个测试（531→556）。
本方案对剩余 40 个无测试模块进行系统性审计。

## 风险评分模型

每个模块按 4 维度打分（1-5），总分 = 各维度之积：

| 维度 | 1 | 3 | 5 |
|------|---|---|---|
| 代码量 | <50行 | 150-300行 | >500行 |
| 复杂度 | 纯计算 | 文件读写 | 并发+外部调用 |
| 暴露面 | 内部工具 | 间接可达 | 直接处理用户输入 |
| 缺测试 | 完整测试 | 部分覆盖 | 零测试 |

## 6 条审计规则

1. **输入边界验证** — API 参数格式校验、文件名/ID/路径 sanitize
2. **文件 I/O 安全** — 路径可控性、临时文件清理、原子写入 fsync
3. **并发与竞态** — 文件锁 TOCTOU、共享状态锁保护、contextvars 正确性
4. **错误处理** — 静默吞错、资源泄漏（未释放锁/未关闭文件）
5. **数据完整性** — JSON/CSV 编码错误、None/NaN/除零
6. **多租户隔离** — get_app_core() vs 直接 import、硬编码路径

## 执行计划

### Phase 1: T1 高危模块（4 个，~1,591 行）

| 模块 | 行数 | 风险分 | 审计重点 |
|------|------|--------|---------|
| chart_executor.py | 499 | 625 | 规则1+2: 代码注入、沙箱逃逸 |
| exam_score_processing_service.py | 532 | 500 | 规则1+5: 数据解析、数值边界 |
| chat_support_service.py | 358 | 400 | 规则1+4: 用户消息、错误吞没 |
| chat_start_service.py | 202 | 300 | 规则3: 会话创建并发、锁竞态 |

### Phase 2: T2 数据层（4 个，~1,397 行）

| 模块 | 行数 | 风险分 | 审计重点 |
|------|------|--------|---------|
| teacher_memory_core.py | 641 | 300 | 规则6+2: 多租户绕过 |
| session_store.py | 243 | 180 | 规则2+3: 持久化竞态 |
| job_repository.py | 183 | 225 | 规则3: 锁 TOCTOU |
| chat_lane_repository.py | 330 | 240 | 规则2+3: 并发写入 |

### Phase 3: T3 基础设施（6 个，~1,029 行）

| 模块 | 审计重点 |
|------|---------|
| tenant_dispatcher/factory/registry | 规则6: 多租户路由隔离 |
| llm_routing_resolver.py | 规则4+5: 路由逻辑边界 |
| paths.py | 规则2: 路径构造安全 |
| config.py | 规则4: 配置加载错误处理 |

### 每个模块的工作流程

1. 读取代码，按 6 条规则逐一检查
2. 记录 bug（位置、严重程度、修复方案）
3. 编写针对性测试
4. 修复 bug
5. 运行全量测试验证

---

## Phase 1 执行结果

审计日期: 2026-02-11 | 测试: 556 → 589 (新增 33)

### 发现汇总

| 模块 | HIGH | MEDIUM | LOW | 已修复 |
|------|------|--------|-----|--------|
| chart_executor.py | 3 | 4 | 4 | 0 (需架构级沙箱) |
| exam_score_processing_service.py | 3 | 4 | 4 | 2 (静默吞错+NaN) |
| chat_start_service.py | 1 | 5 | 3 | 2 (enqueue失败+日志) |
| chat_support_service.py | 0 | 1 | 5 | 0 (低优先级) |

### 关键修复

1. `exam_score_processing_service.py`: `ensure_questions_max_score` 异常加日志;
   `score_objective_answer` 加 NaN/零/负数/Infinity 防护
2. `chat_start_service.py`: `enqueue_chat_job` 失败时标记 job 为 failed;
   3 处 `load_chat_job` 静默回退加 warning 日志

### 待处理（需架构决策）

- chart_executor.py RCE: 需容器/nsjail 沙箱，非代码层面可修
- exam_score_processing_service.py TOCTOU: 需文件锁或原子写入重构
- chat_start_service.py 并发: dedup 和 lane 容量检查的锁粒度优化

---

## Phase 2 执行结果

审计日期: 2026-02-11 | 测试: 589 → 605 (新增 16)

### 发现汇总

| 模块 | HIGH | MEDIUM | LOW | 已修复 |
|------|------|--------|-----|--------|
| teacher_memory_core.py + helpers | 1 | 5 | 5 | 6 (H1+M5) |
| session_store.py | 1 | 5 | 3 | 5 (H1+M4) |
| job_repository.py | 1 | 3 | 3 | 3 (M3) |
| chat_lane_repository.py | 1 | 5 | 3 | 6 (H1+M5) |

### 关键修复

1. `teacher_session_compaction_helpers.py`: `_mark_teacher_session_compacted` 加 session index lock 防止并发覆写;
   `_write_teacher_session_records` 加 fsync; 新增 `_teacher_compact_reset_ts` 允许失败后立即重试;
   `_TEACHER_SESSION_COMPACT_TS` 加 eviction 防止无限增长; 静默 except 加日志
2. `session_store.py`: `append_*_session_message` 改用 `os.open(O_APPEND)` + `os.fsync` 保证原子写入;
   meta 字段过滤 `_RESERVED_META_KEYS` 防止覆写 ts/role/content;
   index loader 去掉 TOCTOU `exists()` 检查，改用 try/except 区分 FileNotFoundError 和 JSONDecodeError
3. `job_repository.py`: `load_*_job` 加 dict 类型校验; `write_*_job` 静默 except 改为 JSONDecodeError + 日志
4. `chat_lane_repository.py`: 所有访问 `CHAT_IDEMPOTENCY_STATE` 的函数加 None 守卫;
   `_chat_request_map_set_if_absent` 加 fsync; TOCTOU `exists()` 改为 try/except;
   `upsert_chat_request_index` 静默 except 加 debug 日志
5. `teacher_memory_core.py`: `teacher_memory_list_proposals` sort lambda 改用 `_safe_mtime` 防止 TOCTOU crash;
   `_teacher_mem0_index_entry` 加 try/except 与兄弟函数一致;
   `_teacher_session_summary_text` 去掉多余 `exists()` 检查;
   `_teacher_memory_context_text` 加 `max_chars <= 0` 早返回

### 待处理（需架构决策）

- ~~job_repository read-modify-write 竞态: 需 lockfile 包裹整个读-改-写流程~~ ✅ 已用 fcntl.flock 修复
- ~~session_store `_SESSION_INDEX_LOCKS` 无限增长: 需 LRU 或 WeakValueDictionary~~ ✅ 已改为 WeakValueDictionary
- ~~chat_lane_repository `CHAT_LANE_CURSOR` int 不可共享引用: 需包装为可变容器~~ ✅ 已改为 `[0]` 列表
- 多租户隔离: session_store/job_repository 使用模块级路径常量，未接入 get_app_core() (runtime_state 镜像模式的根本限制)

---

## Phase 3: 基础设施层 (T3)

### 审计范围
- tenant_registry.py, tenant_dispatcher.py, tenant_app_factory.py
- tenant_config_store.py, tenant_admin_api.py
- wiring/__init__.py, runtime/runtime_state.py
- queue/queue_backend_factory.py, chat_lane_store_factory.py
- workers/rq_tenant_runtime.py

### 发现问题: 16 个 (7 HIGH, 5 MEDIUM, 4 LOW)

### 已修复

1. **tenant_registry.py** TOCTOU 竞态 (HIGH): `get_or_create` 整个创建路径持锁，防止重复创建租户实例
2. **app.py** 多租户初始化异常吞没 (HIGH): 加 `_log.error(..., exc_info=True)` 日志
3. **tenant_dispatcher.py** 无界正则 (HIGH): 收紧为 `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`
4. **tenant_dispatcher.py** 未设 CURRENT_CORE (HIGH): 分发前显式设置 `CURRENT_CORE`
5. **wiring/__init__.py** 默认租户泄漏 (HIGH): 多租户模式下 `CURRENT_CORE` 未设置时抛 RuntimeError
6. **tenant_app_factory.py** shutdown 异常吞没 (MEDIUM): 加 `_log.warning` 日志
7. **tenant_config_store.py** JSON 解析异常吞没 (MEDIUM): get/list 方法加 `_log.warning`
8. **tenant_config_store.py** WAL pragma 失败吞没 (LOW): 加 `_log.warning`
9. **tenant_admin_api.py** 路径穿越 (MEDIUM): 加 `_validate_tenant_path` 守卫
10. **chat_lane_store_factory.py** 无锁竞态 (MEDIUM): 加 `threading.Lock`
11. **queue_backend_factory.py** 全局单例 (HIGH): 改为按 tenant_id 索引的字典 + Lock
12. **rq_tenant_runtime.py** TOCTOU (MEDIUM): 加双重检查锁定
13. **job_repository.py** read-modify-write 竞态: 加 `fcntl.flock` 文件锁
14. **session_store.py** 锁字典无限增长: 改为 `WeakValueDictionary`
15. **chat_lane_repository.py** CURSOR 不可变: 改为 `[0]` 可变列表容器
16. **runtime_state.py** 同步更新 CURSOR 和 WeakValueDictionary 类型

### 已知限制（需更大重构）

- **runtime_state.py 全局单例镜像** (Issue 6): 提取的模块 (chat_lane_repository, profile_service 等) 通过模块级全局变量持有状态，`reset_runtime_state` 镜像写入。多租户模式下后一个租户会覆盖前一个。根本修复需要所有提取模块改为通过 `get_app_core()` 动态查找状态。
- **teacher_provider_registry_service.py** `_LOCKS` 字典无限增长 (LOW): 需 WeakValueDictionary

### 新增测试: 23 个 (`tests/test_tenant_infra.py`)

测试总数: 605 → 628
