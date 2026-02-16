# 2026-02-15 学生侧 mem0 受控记忆与老师私有视角设计

## 背景与目标
当前系统中，教师侧已具备 mem0 检索/写入能力，学生侧在线主链路仍以 `student_profiles` 和会话上下文为主。项目现在决定引入学生侧 mem0 辅助记忆，同时满足三项硬约束：

1. 写入必须 `仅教师确认`，禁止自动落库。
2. 老师视角记忆必须 `老师私有`，不能跨老师共享。
3. 学生记忆白名单采用 `最保守` 模式，仅允许长期稳定信息，不允许具体分数/排名/单次事件进入长期记忆。

设计目标：在不牺牲主链路稳定性的前提下，提高跨会话辅导连续性、教学个性化和可解释性。

## 决策与总分分析
### 方案候选
1. A 严格受控（已选）：仅教师确认写入 + 老师私有视角 + 最保守白名单。
2. B 半自动受控：白名单自动写入，其余审核。
3. C 全自动严格规则：规则命中即写入。

### 量化评分（满分 100）
评分权重：安全性 30、隔离性 25、可解释性 20、实现复杂度 15、运行成本 10。

1. A：92 分（推荐并采纳）
2. B：78 分
3. C：61 分

A 方案主要优势是审计链路完整、误写风险最低、隔离边界最清晰；代价是写入吞吐较低，但可通过批量审核和候选质量优化缓解。

## 架构总览
新增学生记忆能力采用“三层模型”并坚持 `先读后写`：

1. `student_core`（学生稳定记忆层）
内容限定为长期稳定信息：学习偏好、稳定误区、长期目标、已验证有效干预策略。

2. `teacher_view`（老师-学生私有视角层）
仅当前老师可见，用于沉淀该老师对该学生的教学策略与表达偏好，禁止其他老师访问。

3. 检索注入层（RAG 注入）
根据角色决定注入范围：
- 学生会话：仅读 `student_core`
- 教师会话（针对某学生分析）：读 `student_core + 当前 teacher_view`

## 数据模型与命名空间
### 命名空间
1. 学生核心记忆：`tenant:{tenant_id}:student:{student_id}:core`
2. 老师私有视角：`tenant:{tenant_id}:teacher:{teacher_id}:student:{student_id}:view`

说明：强制包含 `tenant_id`，避免多租户中同名 ID 混淆。

### 候选记录（本地提案）
建议字段：
- `proposal_id`
- `tenant_id`
- `teacher_id`
- `student_id`
- `memory_type`（仅白名单四类）
- `content`
- `evidence_refs`（会话/消息证据）
- `risk_flags`
- `status`（proposed/applied/rejected/deleted）
- `created_at`
- `reviewed_at`
- `reviewed_by`

### mem0 metadata 建议
- `tenant_id`
- `teacher_id`（仅 teacher_view 必填）
- `student_id`
- `scope`（core/view）
- `proposal_id`
- `memory_type`
- `source`
- `created_at`

## 受控写入策略
### 白名单（最保守）
仅允许以下四类：
1. 学习偏好（例如讲解节奏、表达形式偏好）
2. 稳定误区（需跨多次证据）
3. 长期目标（阶段目标与计划）
4. 有效干预策略（被验证有效的方法）

### 硬阻断（禁止写入）
触发以下任一条件直接拒绝候选：
1. 具体分数、排名、名次、单次测验结果。
2. 身份证号/手机号/住址/家庭隐私。
3. 健康、心理等敏感信息。
4. 单次偶发事件、缺乏重复证据的信息。

### 去重与衰减
1. 对 `content` 做规范化 + 稳定哈希去重。
2. 同类记忆支持 supersede，避免重复堆积。
3. 配置 TTL 与人工删除并存，优先人工操作。

## 端到端流程
1. 候选生成：会话后处理阶段提取候选，先写提案存储，不写 mem0。
2. 教师审核：教师端逐条 approve/reject/delete。
3. 落库写入：仅 approve 执行 mem0 add。
4. 在线检索：按角色与 scope 检索 top-k，并做去重融合。
5. 删除回滚：删除提案时同步删除 mem0 对应记录，保证“删后不可检索”。

## API 设计（建议）
1. `GET /teacher/student-memory/proposals?student_id=&status=&limit=`
2. `POST /teacher/student-memory/proposals/{proposal_id}/review`
3. `DELETE /teacher/student-memory/proposals/{proposal_id}`
4. `GET /teacher/student-memory/search?student_id=&q=&scope=core|view|both`
5. `GET /teacher/student-memory/insights?student_id=&days=`

约束：`scope=view` 与 `scope=both` 仅返回当前老师的私有视角数据。

## 配置开关（建议默认值）
- `STUDENT_MEM0_ENABLED=0`
- `STUDENT_MEM0_WRITE_ENABLED=0`
- `STUDENT_MEM0_RETRIEVE_TOPK=3`
- `STUDENT_MEM0_THRESHOLD=0.15`
- `STUDENT_MEM0_PROPOSAL_DAILY_CAP=6`
- `STUDENT_MEM0_STRICT_WHITELIST=1`
- `STUDENT_MEM0_REQUIRE_TEACHER_REVIEW=1`
- `STUDENT_MEM0_TEACHER_VIEW_ISOLATED=1`

## 验收指标与上线门槛
### 评分维度（总分 100）
1. 安全合规（30）：违规写入率 < 0.5%，高风险阻断率 100%。
2. 隔离正确性（25）：跨老师泄露 0，跨租户泄露 0。
3. 教学有效性（20）：教师“有帮助”反馈率 >= 70%。
4. 稳定性（15）：mem0 故障不影响主链路，P95 延迟增量 < 120ms。
5. 运维成本（10）：审核平均耗时 < 30 秒/条，删除回滚成功率 100%。

### 发布门槛
1. `>= 85`：允许全量。
2. `70 - 84`：仅灰度，继续迭代。
3. `< 70`：回滚为“仅候选不落库”。

## 分阶段实施清单
### M1（最小闭环，不接 mem0 写入）
1. 新增学生记忆候选提案存储与状态机。
2. 教师端候选列表 + 审核操作 UI。
3. 风险阻断与白名单校验器。
4. 审计日志（proposal lifecycle）。

### M2（接入 mem0）
1. approve -> mem0 add 打通。
2. 学生端/教师端检索注入打通（只读）。
3. scope 隔离检查（tenant + teacher + student）。
4. 故障降级开关（mem0 fail -> fallback）。

### M3（可运维与质量治理）
1. 删除回滚（提案 + mem0 双删）。
2. 质量看板（命中率、误写率、审核耗时）。
3. 灰度发布与回滚预案自动化。
4. 集成测试与越权/串味安全测试。

## 测试策略
1. 单元测试：白名单分类、敏感阻断、去重哈希、scope 解析。
2. 集成测试：propose/review/delete 全流程；删除后不可检索。
3. 安全测试：跨老师、跨租户访问隔离。
4. 回归测试：mem0 down 场景主链路不受影响。

## 风险与回滚
### 主要风险
1. 候选质量不足导致审核负担高。
2. 规则漏拦截造成敏感信息写入。
3. 命名空间不一致导致串味。

### 回滚策略
1. 立即关闭 `STUDENT_MEM0_WRITE_ENABLED`。
2. 保留候选提案，不中断教学功能。
3. 必要时关闭 `STUDENT_MEM0_ENABLED`，回退到现有 profile 路径。

## 下一步
1. 按 M1 开始实现（建议先后端提案 API 与状态机，再接教师端 UI）。
2. 完成 M1 后进行一次小规模灰度验证，再进入 M2。
