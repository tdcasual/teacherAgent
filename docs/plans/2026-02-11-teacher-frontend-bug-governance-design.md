# 2026-02-11 Teacher Frontend Bug 治理设计

日期：2026-02-11  
状态：已评审确认（待进入实施）

## 1. 决策记录

本方案基于已确认的四项决策：

1. 总体路线：`A 风险分层闭环`
2. 范围优先级：`Teacher 端优先`
3. 质量优先级：`体验一致性优先`
4. 节奏：`2 周稳态推进`
5. 执行机制：`M1 指挥台式闭环`

目标不是一次性“修最多问题”，而是建立可持续的“发现 -> 定位 -> 修复 -> 验证 -> 防回归”统一流水线，确保前端重构后系统在可用性与一致性上同时收敛。

## 2. 治理架构

### 2.1 指挥台分流模型

统一使用三泳道处理缺陷：

- `Lane-1 可用性阻塞`：功能不可用、流程中断、数据状态异常
- `Lane-2 体验一致性`：交互行为不一致、状态反馈错位、跨页面行为冲突
- `Lane-3 视觉偏差`：样式/布局偏差、断点表现不稳定

由于本轮优先级为“体验一致性优先”，`Lane-2` 与 `Lane-1` 同级，不作为低优先级尾项处理。

### 2.2 缺陷卡标准字段

每个缺陷必须包含以下字段才能进入开发：

- 缺陷级别（P0/P1/P2）
- 影响模块（Chat/Workbench/Upload/Session）
- 复现步骤（最小闭环）
- 预期行为 / 实际行为
- 根因假设（含置信度 H/M/L）
- 修复 PR 链接
- 回归用例 ID
- 发布观察点（48h）
- 回滚策略

字段不完整的卡片停留在 `New`，不得进入 `Fixing`。

## 3. 模块与组件边界

本轮仅覆盖 Teacher 端，代码入口如下：

- `/Users/lvxiaoer/Documents/New project/frontend/apps/teacher/src/features/chat`
- `/Users/lvxiaoer/Documents/New project/frontend/apps/teacher/src/features/workbench`
- `/Users/lvxiaoer/Documents/New project/frontend/apps/teacher/src/features/state`

按四域治理：

1. `Chat 域`：输入解析、pending 生命周期、状态轮询恢复、跨 session 绑定
2. `Workbench 域`：技能/路由状态一致、模式隔离、交互反馈稳定
3. `Upload 域`：start/status/draft/confirm 状态机一致、刷新恢复、终态清理
4. `Session 域`：会话菜单、侧栏联动、移动端 overlay 与焦点路径

## 4. 数据流与状态流转

### 4.1 缺陷生命周期

统一看板状态：

`New -> Triaged -> Fixing -> Ready for Verify -> Verified -> Released -> Observing(48h) -> Closed`

任何回退必须写明原因（如：复现条件变更、回归 case 不稳定、根因误判）。

### 4.2 输入与输出

输入源：

- E2E 失败记录（优先级最高）
- 手工回归记录
- 线上日志/告警
- 产品验收反馈

输出件：

- 修复 PR
- 回归测试 ID（自动化或手工）
- 发布观察点
- 风险台账更新

### 4.3 根因置信度机制

- `H`：证据充分，可直接进入修复
- `M`：允许修复，但必须附加观测点
- `L`：禁止直接发版，需先补证据或保护性日志

## 5. 错误处理与风控策略

1. 严格禁止“猜修”直接上线：每个缺陷必须有最小复现证据（录屏/HAR/控制台日志/最小步骤）
2. 置信度为 `L` 的修复必须经过额外验证轮（含跨域 smoke）
3. 发布后进入 48h 观察窗，出现同类症状自动 reopen 并升级优先级
4. 统一记录“误判根因”案例，避免重复投入同类无效修复

## 6. 测试与门禁设计

### 6.1 验证顺序（固定）

1. `npm run typecheck`
2. Teacher 目标域 E2E（按变更域执行）
3. 跨域 smoke（Chat + Workbench + Upload 各至少 1 条）

仅当三步全部通过，缺陷状态才可从 `Ready for Verify` 进入 `Verified`。

### 6.2 回归资产复用与扩展

优先扩展现有用例文件：

- `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-chat-chaos.spec.ts`
- `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-workbench-regression.spec.ts`
- `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-upload-lifecycle.spec.ts`
- `/Users/lvxiaoer/Documents/New project/frontend/e2e/teacher-recovery-state.spec.ts`

P0 要求：每个已修复缺陷至少绑定 1 条自动化回归。  
P1 要求：高频交互一致性问题补齐异常路径（弱网/刷新/并发点击/localStorage 异常）。

## 7. 两周实施计划

### Week 1（P0 清零 + 门禁固化）

- D1：基线审计（现有 E2E 失败、线上高频问题、手工复现池）
- D2-D3：Chat + Upload P0 修复
- D4：Session + Workbench P0 修复
- D5：仅验证与发版观察点加固（不新增需求）

### Week 2（P1 收敛 + 稳定性收口）

- D6-D8：交互一致性与视觉回归高频项
- D9：跨域回归 + flaky case 收敛
- D10：稳定性复盘 + 下轮 Backlog 冻结

## 8. 角色分工

最小职责配置：

1. `Triage Owner`：分级与优先级拍板
2. `Domain Owner`：按域修复与技术决策
3. `Verification Owner`：复现证据与回归放行
4. `Release Owner`：发布窗口管理与 48h 观察

同一缺陷仅允许一个 Owner，防止“多人关注但无人负责”。

## 9. 完成定义（DoD）与指标

### 9.1 DoD

缺陷关闭必须同时满足：

1. 缺陷卡字段完整
2. 至少 1 条自动化回归通过
3. 关键路径手工验证通过
4. 发布后 48h 无复发

### 9.2 量化指标

- P0 平均修复时长：`<= 24h`
- 回归通过率：`>= 95%`
- flaky 比例：`<= 5%`
- reopen 比例：`<= 10%`
- 跨域阻塞问题：周环比下降

这些指标用于判定“治理体系是否生效”，不是单纯统计修复数量。

## 10. 风险与边界

1. 若短期内追求吞吐而弱化 triage，会导致一致性问题反复回归
2. 若缺少发布观察点，低置信度修复会在生产环境反复 reopen
3. 若回归门禁未固化到日常流程，两周后质量将回到重构后波动状态

## 11. 下一步（实施入口）

1. 按四域创建初始缺陷池并完成首轮分级（P0/P1/P2）
2. 将 Week 1 的 P0 项映射到现有 E2E spec，并补齐缺失 case
3. 启动每日固定 triage 与收口复盘，按本设计执行状态流转
